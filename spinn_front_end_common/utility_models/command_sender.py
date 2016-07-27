# pacman imports
from pacman.model.decorators.overrides import overrides
from pacman.executor.injection_decorator import \
    supports_injection, requires_injection, inject
from pacman.model.abstract_classes.impl.constrained_object import \
    ConstrainedObject
from pacman.model.constraints.abstract_provides_outgoing_partition_constraints\
    import AbstractProvidesOutgoingPartitionConstraints
from pacman.model.constraints.key_allocator_constraints.\
    key_allocator_fixed_key_and_mask_constraint \
    import KeyAllocatorFixedKeyAndMaskConstraint
from pacman.model.constraints.key_allocator_constraints.\
    key_allocator_fixed_mask_constraint \
    import KeyAllocatorFixedMaskConstraint
from pacman.model.decorators.delegates_to import delegates_to
from pacman.model.graphs.application.abstract_application_vertex import \
    AbstractApplicationVertex
from pacman.model.resources.resource_container import ResourceContainer
from pacman.model.resources.sdram_resource import SDRAMResource
from pacman.model.routing_info.base_key_and_mask import BaseKeyAndMask

# spinn front end common imports
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.abstract_models.impl.data_specable_vertex import \
    DataSpecableVertex
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utility_models.command_sender_machine_vertex \
    import CommandSenderMachineVertex


@supports_injection
class CommandSender(
        AbstractProvidesOutgoingPartitionConstraints,
        AbstractApplicationVertex, DataSpecableVertex):
    """ A utility for sending commands to a vertex (possibly an external\
        device) at fixed times in the simulation
    """

    def __init__(self, machine_time_step, timescale_factor, label):

        AbstractProvidesOutgoingPartitionConstraints.__init__(self)
        DataSpecableVertex.__init__(
            self, machine_time_step, timescale_factor)
        AbstractApplicationVertex.__init__(self)

        self._commands_by_edge = dict()

        # storage objects
        self._graph_mapper = None
        self._machine_graph = None
        self._routing_info = None
        self._label = label

        # impl for where constraints are stored
        self._constraints = ConstrainedObject()

    @delegates_to("_constraints", ConstrainedObject.add_constraint)
    def add_constraint(self, constraint):
        pass

    @delegates_to("_constraints", ConstrainedObject.add_constraints)
    def add_constraints(self, constraints):
        pass

    @delegates_to("_constraints", ConstrainedObject.constraints)
    def constraints(self):
        pass

    def add_commands(self, commands, edge):
        """ Add commands to be sent down a given edge

        :param commands: The commands to send
        :type commands: iterable of\
                    :py:class:`spinn_front_end_common.utility_models.multi_cast_command.MultiCastCommand`
        :param edge: The edge down which the commands will be sent
        :type edge:\
                    :py:class:`pacman.model.graph.application.abstract_application_edge.AbstractApplicationEdge`
        :raise ConfigurationException:\
            If the edge already has commands or if all the commands masks are\
            not 0xFFFFFFFF and there is no commonality between the\
            command masks
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

    @overrides(DataSpecableVertex.generate_data_specification)
    @requires_injection(
        ["MemoryGraphMapper", "MemoryMachineGraph", "MemoryRoutingInfo"])
    def generate_data_specification(self, spec, placement):

        # reserve region - add a word for the region size
        n_command_bytes = self._get_n_command_bytes()
        self._reserve_memory_regions(
            spec, n_command_bytes + 4, placement.vertex)

        # Write system region
        spec.comment("\n*** Spec for multicast source ***\n\n")
        self._write_basic_setup_info(
            spec, CommandSenderMachineVertex.SYSTEM_REGION)

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
        spec.switch_write_focus(region=CommandSenderMachineVertex.COMMANDS)
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
                spec.write_value(self._get_key(command))
                payload = command.get_payload(
                    self._routing_info, self._machine_graph, self._graph_mapper)
                spec.write_value(payload)
                spec.write_value(command.repeat << 16 |
                                 command.delay_between_repeats)

            spec.write_value(len(without_payload))
            for command in without_payload:
                spec.write_value(self._get_key(command))
                spec.write_value(command.repeat << 16 |
                                 command.delay_between_repeats)

        # End-of-Spec:
        spec.end_specification()

    def _get_key(self, command):
        """ Return a key for a command

        :param command:
        :return:
        """

        if command.mask == 0xFFFFFFFF:
            return command.key

        # Find the routing info for the edge.  Note that this assumes that
        # all the edges have the same keys assigned
        edge_for_command = self._command_edge[command]
        machine_edge_for_command = iter(
            self._graph_mapper.get_machine_edges(edge_for_command)).next()
        key = \
            self._routing_info.get_first_key_for_edge(machine_edge_for_command)

        # Build the command by merging in the assigned key with the command
        return key | command.key

    @requires_injection(["MemoryGraphMapper"])
    @overrides(AbstractProvidesOutgoingPartitionConstraints.
               get_outgoing_partition_constraints)
    def get_outgoing_partition_constraints(self, partition):
        """

        :param partition:
        :return:
        """
        edge = self._graph_mapper.get_application_edge(
            partition.edges[0])
        if edge in self._edge_constraints:
            return self._edge_constraints[edge]
        return list()

    @staticmethod
    def _reserve_memory_regions(spec, command_size, vertex):
        """
        Reserve SDRAM space for memory areas:
        1) Area for information on what data to record
        2) area for start commands
        3) area for end commands
        """
        spec.comment("\nReserving memory space for data regions:\n\n")

        # Reserve memory:
        spec.reserve_memory_region(
            region=CommandSenderMachineVertex.SYSTEM_REGION,
            size=constants.DATA_SPECABLE_BASIC_SETUP_INFO_N_WORDS * 4,
            label='setup')
        if command_size > 0:
            spec.reserve_memory_region(
                region=CommandSenderMachineVertex.COMMANDS,
                size=command_size, label='commands')
        vertex.reserve_provenance_data_region(spec)

    @property
    def model_name(self):
        """ Return the name of the model as a string
        """
        return "command_sender_multi_cast_source"

    @overrides(AbstractApplicationVertex.create_machine_vertex)
    def create_machine_vertex(
            self, vertex_slice, resources_required, constraints=None):
        return CommandSenderMachineVertex(
            constraints, resources_required, self.label)

    @overrides(AbstractApplicationVertex.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(self, vertex_slice):

        sdram = (
            self._get_n_command_bytes() + 4 + 12 +
            CommandSenderMachineVertex.get_provenance_data_size(0)
        )

        # Return the SDRAM and 1 core
        return ResourceContainer(sdram=SDRAMResource(sdram))

    @property
    @overrides(AbstractApplicationVertex.n_atoms)
    def n_atoms(self):
        return 1

    @overrides(DataSpecableVertex.get_binary_file_name)
    def get_binary_file_name(self):
        """ Return a string representation of the models binary

        :return:
        """
        return 'command_sender_multicast_source.aplx'

    @inject("MemoryGraphMapper")
    def set_graph_mapper(self, graph_mapper):
        self._graph_mapper = graph_mapper

    @inject("MemoryMachineGraph")
    def set_machine_graph(self, machine_graph):
        self._machine_graph = machine_graph

    @inject("MemoryRoutingInfo")
    def set_routing_info(self, routing_info):
        self._routing_info = routing_info

    @property
    @overrides(AbstractApplicationVertex.label)
    def label(self):
        return self._label
