# pacman imports
from pacman.model.routing_info.base_key_and_mask import BaseKeyAndMask
from pacman.model.constraints.key_allocator_constraints.\
    key_allocator_fixed_mask_constraint \
    import KeyAllocatorFixedMaskConstraint
from pacman.model.constraints.key_allocator_constraints.\
    key_allocator_fixed_key_and_mask_constraint \
    import KeyAllocatorFixedKeyAndMaskConstraint
from pacman.model.partitionable_graph.abstract_partitionable_vertex\
    import AbstractPartitionableVertex

# data spec imports
from data_specification.data_specification_generator \
    import DataSpecificationGenerator

# spinn front end common imports
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.abstract_models.abstract_data_specable_vertex \
    import AbstractDataSpecableVertex
from spinn_front_end_common.abstract_models.\
    abstract_provides_outgoing_partition_constraints \
    import AbstractProvidesOutgoingPartitionConstraints
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utility_models.command_sender_partitioned_vertex \
    import CommandSenderPartitionedVertex


_COMMAND_WITH_PAYLOAD_SIZE = 12

_COMMAND_WITHOUT_PAYLOAD_SIZE = 8


class CommandSender(AbstractProvidesOutgoingPartitionConstraints,
                    AbstractPartitionableVertex,
                    AbstractDataSpecableVertex):
    """ A utility for sending commands to a vertex (possibly an external\
        device) at fixed times in the simulation
    """

    def __init__(self, machine_time_step, timescale_factor):

        AbstractProvidesOutgoingPartitionConstraints.__init__(self)
        AbstractPartitionableVertex.__init__(
            self, 1, "Command Sender", 1)
        AbstractDataSpecableVertex.__init__(
            self, machine_time_step, timescale_factor)

        self._edge_constraints = dict()
        self._command_edge = dict()
        self._times_with_commands = set()
        self._commands_with_payloads = dict()
        self._commands_without_payloads = dict()

    def create_subvertex(
            self, vertex_slice, resources_required, label=None,
            constraints=None):
        return CommandSenderPartitionedVertex(
            resources_required, label, constraints)

    def add_commands(self, commands, edge):
        """ Add commands to be sent down a given edge

        :param commands: The commands to send
        :type commands: iterable of\
                    :py:class:`spynnaker.pyNN.utilities.multi_cast_command.MultiCastCommand`
        :param edge: The edge down which the commands will be sent
        :type edge:\
                    :py:class:`pacman.model.partitionable_graph.partitionable_edge.PartitionableEdge`
        :raise SpynnakerException: If the edge already has commands or if all\
                    the commands masks are not 0xFFFFFFFF and there is no\
                    commonality between the command masks
        """

        # Check if the edge already exists
        if edge in self._edge_constraints:
            raise exceptions.ConfigurationException(
                "The edge has already got commands")

        # Go through the commands
        command_keys = dict()
        command_mask = 0
        for command in commands:

            # Add the command to the appropriate dictionary
            dictionary = None
            if command.is_payload:
                dictionary = self._commands_with_payloads
            else:
                dictionary = self._commands_without_payloads
            if command.time not in dictionary:
                dictionary[command.time] = list()
            dictionary[command.time].append(command)

            # Add that there is a command at this time
            self._times_with_commands.add(command.time)

            # Add the edge associated with the command
            self._command_edge[command] = edge

            if command.key not in command_keys:

                # If this command has not been seen before, add it
                command_keys[command.key] = command.mask
            else:

                # Otherwise merge the current key mask with the current mask
                command_keys[command.key] = (command_keys[command.key] |
                                             command.mask)

            # Keep track of the masks on all the commands
            command_mask |= command.mask

        if command_mask != 0xFFFFFFFF:

            # If the final command mask contains don't cares, use this as a
            # fixed mask
            self._edge_constraints[edge] = list(
                [KeyAllocatorFixedMaskConstraint(command_mask)])
        else:

            # If there is no mask consensus, check that all the masks are
            # actually 0xFFFFFFFF, as otherwise it will not be possible
            # to assign keys to the edge
            for (key, mask) in command_keys:
                if mask != 0xFFFFFFFF:
                    raise exceptions.ConfigurationException(
                        "Command masks are too different to make a mask"
                        " consistent with all the keys.  This can be resolved"
                        " by either specifying a consistent mask, or by using"
                        " the mask 0xFFFFFFFF and providing exact keys")

            # If the keys are all fixed keys, keep them
            self._edge_constraints[edge] = list([
                KeyAllocatorFixedKeyAndMaskConstraint(
                    [BaseKeyAndMask(key, mask)
                     for (key, mask) in command_keys])])

    def generate_data_spec(
            self, subvertex, placement, partitioned_graph, graph, routing_info,
            hostname, graph_mapper, report_folder, ip_tags, reverse_ip_tags,
            write_text_specs, application_run_time_folder):
        """
        :param subvertex:
        :param placement:
        :param partitioned_graph:
        :param graph:
        :param routing_info:
        :param hostname:
        :param graph_mapper:
        :param report_folder:
        :param ip_tags:
        :param reverse_ip_tags:
        :param write_text_specs:
        :param application_run_time_folder:
        :return:
        """

        data_writer, report_writer = \
            self.get_data_spec_file_writers(
                placement.x, placement.y, placement.p, hostname, report_folder,
                write_text_specs, application_run_time_folder)

        spec = DataSpecificationGenerator(data_writer, report_writer)

        # reserve region - add a word for the region size
        n_command_bytes = self._get_n_command_bytes()
        self._reserve_memory_regions(spec, n_command_bytes + 4, subvertex)

        # Write system region
        spec.comment("\n*** Spec for multicast source ***\n\n")
        self._write_basic_setup_info(
            spec, CommandSenderPartitionedVertex.SYSTEM_REGION)

        # Go through the times and replace negative times with positive ones
        new_times = set()
        for time in self._times_with_commands:
            if time < 0 and self._no_machine_time_steps is not None:
                real_time = self._no_machine_time_steps + (time + 1)
                if time in self._commands_with_payloads:
                    if real_time in self._commands_with_payloads:
                        self._commands_with_payloads[real_time].extend(
                            self._commands_with_payloads[time])
                    else:
                        self._commands_with_payloads[real_time] = \
                            self._commands_with_payloads[time]
                    del self._commands_with_payloads[time]
                if time in self._commands_without_payloads:
                    if real_time in self._commands_without_payloads:
                        self._commands_without_payloads[real_time].extend(
                            self._commands_without_payloads[time])
                    else:
                        self._commands_without_payloads[real_time] = \
                            self._commands_without_payloads[time]
                    del self._commands_without_payloads[time]
                new_times.add(real_time)

            # if runtime is infinite, then there's no point storing end of
            # simulation events, as they will never occur
            elif time < 0 and self._no_machine_time_steps is None:
                if time in self._commands_with_payloads:
                    del self._commands_with_payloads[time]
                if time in self._commands_without_payloads:
                    del self._commands_without_payloads[time]
            else:
                new_times.add(time)

        # write commands
        spec.switch_write_focus(region=CommandSenderPartitionedVertex.COMMANDS)
        spec.write_value(n_command_bytes)
        for time in sorted(new_times):

            # Gather the different types of commands
            with_payload = list()
            if time in self._commands_with_payloads:
                with_payload = self._commands_with_payloads[time]
            without_payload = list()
            if time in self._commands_without_payloads:
                without_payload = self._commands_without_payloads[time]

            spec.write_value(time)

            spec.write_value(len(with_payload))
            for command in with_payload:
                spec.write_value(self._get_key(
                    command, graph_mapper, routing_info, partitioned_graph))
                payload = command.get_payload(routing_info, partitioned_graph,
                                              graph_mapper)
                spec.write_value(payload)
                spec.write_value(command.repeat << 16 |
                                 command.delay_between_repeats)

            spec.write_value(len(without_payload))
            for command in without_payload:
                spec.write_value(self._get_key(
                    command, graph_mapper, routing_info, partitioned_graph))
                spec.write_value(command.repeat << 16 |
                                 command.delay_between_repeats)

        # End-of-Spec:
        spec.end_specification()
        data_writer.close()

        return data_writer.filename

    def _get_key(self, command, graph_mapper, routing_info, partitioned_graph):
        """ Return a key for a command

        :param command:
        :param graph_mapper:
        :param routing_info:
        :return:
        """

        if command.mask == 0xFFFFFFFF:
            return command.key

        # Find the routing info for the edge.  Note that this assumes that
        # all the partitioned edges have the same keys assigned
        edge_for_command = self._command_edge[command]
        partitioned_edge_for_command = iter(
            graph_mapper.get_partitioned_edges_from_partitionable_edge(
                edge_for_command)).next()
        partition = partitioned_graph.\
            get_partition_of_subedge(partitioned_edge_for_command)
        routing_info_for_edge = routing_info.get_keys_and_masks_from_partition(
            partition)

        # Assume there is only one key and mask
        # TODO: Deal with multiple keys and masks
        key_and_mask = routing_info_for_edge[0]

        # Build the command by merging in the assigned key with the command
        return key_and_mask.key | command.key

    def _get_n_command_bytes(self):
        """

        :return:
        """
        n_bytes = 0

        for time in self._times_with_commands:

            # Add 3 words for count-with-command, count-without-command
            # and time
            n_bytes += 12

            # Add the size of each command
            if time in self._commands_with_payloads:
                n_bytes += (len(self._commands_with_payloads[time]) *
                            _COMMAND_WITH_PAYLOAD_SIZE)
            if time in self._commands_without_payloads:
                n_bytes += (len(self._commands_without_payloads[time]) *
                            _COMMAND_WITHOUT_PAYLOAD_SIZE)

        return n_bytes

    def get_outgoing_partition_constraints(self, partition, graph_mapper):
        """

        :param partition:
        :param graph_mapper:
        :return:
        """
        edge = graph_mapper.get_partitionable_edge_from_partitioned_edge(
            partition.edges[0])
        if edge in self._edge_constraints:
            return self._edge_constraints[edge]
        return list()

    def _reserve_memory_regions(self, spec, command_size, subvertex):
        """
        Reserve SDRAM space for memory areas:
        1) Area for information on what data to record
        2) area for start commands
        3) area for end commands
        """
        spec.comment("\nReserving memory space for data regions:\n\n")

        # Reserve memory:
        spec.reserve_memory_region(
            region=CommandSenderPartitionedVertex.SYSTEM_REGION,
            size=constants.DATA_SPECABLE_BASIC_SETUP_INFO_N_WORDS * 4,
            label='setup')
        if command_size > 0:
            spec.reserve_memory_region(
                region=CommandSenderPartitionedVertex.COMMANDS,
                size=command_size, label='commands')
        subvertex.reserve_provenance_data_region(spec)

    @property
    def model_name(self):
        """ Return the name of the model as a string
        """
        return "command_sender_multi_cast_source"

    # inherited from partitionable vertex
    def get_cpu_usage_for_atoms(self, vertex_slice, graph):
        """ Return how much cpu is used by the model for a given number of\
            atoms

        :param vertex_slice: the slice from the partitionable vertex that this\
                    model needs to deduce how many resources it will use
        :param graph: the partitionable graph
        :return: the size of cpu this model is expecting to use for the\
                    number of atoms.
        """
        return 0

    def get_sdram_usage_for_atoms(self, vertex_slice, graph):
        """ Return how much SDRAM is used by the model for a given number of\
            atoms

        :param vertex_slice: the slice from the partitionable vertex that this\
                    model needs to deduce how many resources it will use
        :param graph: the partitionable graph
        :return: the size of SDRAM this model is expecting to use for the\
                    number of atoms.
        """

        # Add a word for the size of the command region,
        # and the size of the system region
        return (
            self._get_n_command_bytes() + 4 + 12 +
            CommandSenderPartitionedVertex.get_provenance_data_size(0))

    def get_dtcm_usage_for_atoms(self, vertex_slice, graph):
        """ Return how much DTCM is used by the model for a given number of\
            atoms

        :param vertex_slice: the slice from the partitionable vertex that this\
                    model needs to deduce how many resources it will use
        :param graph: the partitionable graph
        :return: the size of DTCM this model is expecting to use for the\
                    number of atoms.
        """
        return 0

    def get_binary_file_name(self):
        """ Return a string representation of the models binary

        :return:
        """
        return 'command_sender_multicast_source.aplx'

    def is_data_specable(self):
        """ Helper method for is instance
        :return:
        """
        return True
