"""
command sender
"""

# pacman imports
from pacman.model.partitionable_graph.abstract_partitionable_vertex\
    import AbstractPartitionableVertex
from pacman.model.partitioned_graph.partitioned_vertex import PartitionedVertex

from spinn_front_end_common.abstract_models\
    .abstract_data_specable_partitioned_vertex \
    import AbstractDataSpecablePartitionedVertex
from spinn_front_end_common.utilities import simulation_utilities
from spinn_front_end_common.abstract_models.abstract_executable \
    import AbstractExecutable
from spinn_front_end_common.interface.has_n_machine_timesteps \
    import HasNMachineTimesteps
from spinn_front_end_common.utilities import data_spec_utilities
from spinn_front_end_common.utility_models.command_paritionable_edge \
    import CommandPartitionableEdge
from spinn_front_end_common.utility_models.command_partitioned_edge \
    import CommandPartitionedEdge

# data spec imports
from data_specification.data_specification_generator \
    import DataSpecificationGenerator

# general imports
from enum import Enum


_COMMAND_WITH_PAYLOAD_SIZE = 12

_COMMAND_WITHOUT_PAYLOAD_SIZE = 8


class CommandSender(AbstractPartitionableVertex,
                    AbstractDataSpecablePartitionedVertex,
                    AbstractExecutable,
                    PartitionedVertex,
                    HasNMachineTimesteps):
    """ A utility for sending commands to a vertex (possibily an external\
        device) at fixed times in the simulation
    """

    _COMMAND_SENDER_REGIONS = Enum(
        value="_COMMAND_SENDER_REGIONS",
        names=[('HEADER', 0),
               ('COMMANDS', 1)])

    def __init__(self, machine_time_step, timescale_factor):
        AbstractPartitionableVertex.__init__(self, 1, "Command Sender", 1)
        AbstractDataSpecablePartitionedVertex.__init__(self)
        AbstractExecutable.__init__(self)
        PartitionedVertex.__init__(self, None, "Command Sender")
        HasNMachineTimesteps.__init__(self)

        self._machine_time_step = machine_time_step
        self._timescale_factor = timescale_factor
        self._times_with_commands = set()
        self._commands_with_payloads = dict()
        self._commands_without_payloads = dict()

        self._command_edge = dict()

    def _add_commands(self, commands, edge):
        """ Add commands to be sent down an edge
        """

        # Go through the commands and add them
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

            self._command_edge[command] = edge

    def add_commands_to_partitionable_vertex(self, commands, vertex):
        """ Add commands to be sent to a given partitionable vertex

        :param commands: The commands to send
        :type commands: iterable of\
                    :py:class:`spinn_front_end_common.utility_models.multi_cast_command.MultiCastCommand`
        :param vertex: The partitionable vertex to send the commands
        :type vertex:\
                    :py:class:`pacman.model.partitionable_graph.abstract_partitionable_vertex.AbstractPartitionableVertex`
        :return: A partitionable edge to the vertex that will send the commands
        """
        edge = CommandPartitionableEdge(self, vertex, commands)
        self._add_commands(commands, edge)
        return edge

    def add_commands_to_partitioned_vertex(self, commands, vertex):
        """ Add commands to be sent to a given partitioned vertex

        :param commands: The commands to send
        :type commands: iterable of\
                    :py:class:`spinn_front_end_common.utility_models.multi_cast_command.MultiCastCommand`
        :param vertex: The partitioned vertex to send the commands
        :type vertex:\
                    :py:class:`pacman.model.partitioned_graph.partitioned_vertex.PartitionedVertex`
        :return: A partitioned edge to the vertex that will send the commands
        """
        edge = CommandPartitionedEdge(self, vertex, commands)
        self._add_commands(commands, edge)
        return edge

    def generate_data_spec(
            self, placement, graph, routing_info, ip_tags, reverse_ip_tags,
            report_folder, output_folder, write_text_specs):
        """
        """
        data_path, data_writer = data_spec_utilities.get_data_spec_data_writer(
            placement, output_folder)
        report_writer = None
        if write_text_specs:
            report_writer = data_spec_utilities.get_data_spec_report_writer(
                placement, report_folder)
        spec = DataSpecificationGenerator(data_writer, report_writer)

        # reserve region - add a word for the region size
        n_command_bytes = self._get_n_command_bytes()
        self._reserve_memory_regions(spec, n_command_bytes + 4)

        # Write system region
        spec.comment("\n*** Spec for multi cast source ***\n\n")
        simulation_utilities.simulation_write_header(
            spec, self._COMMAND_SENDER_REGIONS.HEADER.value,
            "command_sender", self._machine_time_step, self._timescale_factor,
            self.n_machine_timesteps)

        # Go through the times and replace negative times with positive ones
        new_times = set()
        for time in self._times_with_commands:
            if time < 0:
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
            else:
                new_times.add(time)

        # write commands
        spec.switch_write_focus(region=self.COMMANDS)
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
                spec.write_value(self._get_key(command, routing_info))
                payload = command.get_payload(routing_info, graph)
                spec.write_value(payload)
                spec.write_value(command.repeat << 16 |
                                 command.delay_between_repeats)

            spec.write_value(len(without_payload))
            for command in without_payload:
                spec.write_value(self._get_key(command, routing_info))
                spec.write_value(command.repeat << 16 |
                                 command.delay_between_repeats)

        # End-of-Spec:
        spec.end_specification()
        data_writer.close()
        if write_text_specs:
            report_writer.close()

        return data_path

    def _get_key(self, command, routing_info):
        """ Get a key for a command

        :param command: the command to locate the key for
        :param graph_mapper: the mappings between parttiionable and\
                    partitioned graphs
        :param routing_info: the routing infos object
        :return: the key for the command
        """

        if command.mask == 0xFFFFFFFF:
            return command.key

        # Find the routing info for the edge.  Note that this assumes that
        # all the partitioned edges have the same keys assigned
        edge_for_command = self._command_edge[command]

        # TODO: Deal with multiple partitioned edges
        partitioned_edge_for_command = None
        if isinstance(edge_for_command, CommandPartitionedEdge):
            partitioned_edge_for_command = edge_for_command
        elif isinstance(edge_for_command, CommandPartitionableEdge):
            partitioned_edge_for_command = \
                edge_for_command.partitioned_edges[0]

        routing_info_for_edge = (
            routing_info.get_keys_and_masks_from_subedge(
                partitioned_edge_for_command))

        # Assume there is only one key and mask
        # TODO: Deal with multiple keys and masks
        key_and_mask = routing_info_for_edge[0]

        # Build the command by merging in the assigned key with the command
        return key_and_mask | command.key

    def _get_n_command_bytes(self):
        """ Calculate the size of memory in bytes that the commands require
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

    def _reserve_memory_regions(self, spec, command_size):
        """
        """
        spec.comment("\nReserving memory space for data regions:\n\n")

        # Reserve memory:
        simulation_utilities.simulation_reserve_header(
            spec, self._COMMAND_SENDER_REGIONS.HEADER.value)
        if command_size > 0:
            spec.reserve_memory_region(
                region=self._COMMAND_SENDER_REGIONS.COMMANDS.value,
                size=command_size, label='commands')

    @property
    def model_name(self):
        """
        """
        return "command_sender_multi_cast_source"

    # inherited from partitionable vertex
    def get_cpu_usage_for_atoms(self, vertex_slice, graph):
        """
        """
        return 0

    def get_sdram_usage_for_atoms(self, vertex_slice, graph):
        """
        """

        # Add a word for the size of the command region,
        # and the size of the system region
        return (self._get_n_command_bytes() + 4 +
                simulation_utilities.HEADER_REGION_BYTES)

    def get_dtcm_usage_for_atoms(self, vertex_slice, graph):
        """
        """
        return 0

    def get_binary_file_name(self):
        """
        """
        return 'command_sender_multicast_source.aplx'
