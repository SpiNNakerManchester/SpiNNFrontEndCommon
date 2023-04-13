# Copyright (c) 2016 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from enum import IntEnum
from spinn_utilities.overrides import overrides
from pacman.model.graphs.machine import MachineVertex, MachineEdge
from pacman.model.resources import ConstantSDRAM
from pacman.model.routing_info import BaseKeyAndMask
from spinn_front_end_common.abstract_models import (
    AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.provenance import (
    ProvidesProvenanceDataFromMachineImpl, ProvenanceWriter)
from spinn_front_end_common.interface.simulation.simulation_utilities import (
    get_simulation_header_array)
from spinn_front_end_common.utilities.constants import (
    SYSTEM_BYTES_REQUIREMENT, SIMULATION_N_BYTES, BYTES_PER_WORD)
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.utility_objs import (
    ExecutableType)


class CommandSenderMachineVertex(
        MachineVertex, ProvidesProvenanceDataFromMachineImpl,
        AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification):
    """
    Machine vertex for injecting packets at particular times or in
    response to particular events into a SpiNNaker application.
    """
    # Regions for populations
    class DATA_REGIONS(IntEnum):
        SYSTEM_REGION = 0
        COMMANDS_WITH_ARBITRARY_TIMES = 1
        COMMANDS_AT_START_RESUME = 2
        COMMANDS_AT_STOP_PAUSE = 3
        PROVENANCE_REGION = 4

    # 4 for key, 4 for has payload, 4 for payload 4 for repeats, 4 for delays
    _COMMAND_WITH_PAYLOAD_SIZE = 5 * BYTES_PER_WORD

    # 4 for the time stamp
    _COMMAND_TIMESTAMP_SIZE = BYTES_PER_WORD

    # 4 for the int to represent the number of commands
    _N_COMMANDS_SIZE = BYTES_PER_WORD

    # bool for if the command has a payload (true = 1)
    _HAS_PAYLOAD = 1

    # bool for if the command does not have a payload (false = 0)
    _HAS_NO_PAYLOAD = 0

    # The name of the binary file
    BINARY_FILE_NAME = 'command_sender_multicast_source.aplx'

    # all commands will use this mask
    _DEFAULT_COMMAND_MASK = 0xFFFFFFFF

    def __init__(self, label, app_vertex=None):
        """
        :param str label: The label of this vertex
        :param CommandSender app_vertex:
        """
        super().__init__(label, app_vertex)

        self._timed_commands = list()
        self._commands_at_start_resume = list()
        self._commands_at_pause_stop = list()
        self._keys_to_partition_id = dict()
        self._partition_id_keys = dict()
        self._edge_partition_id_counter = 0
        self._vertex_to_key_map = dict()

    def add_commands(
            self, start_resume_commands, pause_stop_commands,
            timed_commands, vertex_to_send_to):
        """
        Add commands to be sent down a given edge.

        :param iterable(MultiCastCommand) start_resume_commands:
            The commands to send when the simulation starts or resumes from
            pause
        :param iterable(MultiCastCommand) pause_stop_commands:
            the commands to send when the simulation stops or pauses after
            running
        :param iterable(MultiCastCommand) timed_commands:
            The commands to send at specific times
        :param ~pacman.model.graphs.AbstractVertex vertex_to_send_to:
            The vertex these commands are to be sent to
        """
        # container for keys for partition mapping (remove duplicates)
        command_keys = set()
        self._vertex_to_key_map[vertex_to_send_to] = set()

        # update holders
        self._commands_at_start_resume.extend(start_resume_commands)
        self._commands_at_pause_stop.extend(pause_stop_commands)
        self._timed_commands.extend(timed_commands)

        for commands in (
                start_resume_commands, pause_stop_commands, timed_commands):
            for command in commands:
                # track keys
                command_keys.add(command.key)
                self._vertex_to_key_map[vertex_to_send_to].add(command.key)

        # create mapping between keys and partitions via partition constraint
        for key in command_keys:
            if key not in self._keys_to_partition_id:
                partition_id = f"COMMANDS{self._edge_partition_id_counter}"
                self._keys_to_partition_id[key] = partition_id
                self._partition_id_keys[partition_id] = key
                self._edge_partition_id_counter += 1

    def get_fixed_key_and_mask(self, partition_id):
        """
        Get the key and mask for the given partition.

        :param str partition_id: The partition to get the key for
        :rtype: ~pacman.model.routing_info.BaseKeyAndMask
        """
        return BaseKeyAndMask(
            self._partition_id_keys[partition_id], self._DEFAULT_COMMAND_MASK)

    @property
    @overrides(ProvidesProvenanceDataFromMachineImpl._provenance_region_id)
    def _provenance_region_id(self):
        return self.DATA_REGIONS.PROVENANCE_REGION

    @property
    @overrides(ProvidesProvenanceDataFromMachineImpl._n_additional_data_items)
    def _n_additional_data_items(self):
        return 1

    @property
    @overrides(MachineVertex.sdram_required)
    def sdram_required(self):
        sdram = (
            self.get_timed_commands_bytes() +
            self.get_n_command_bytes(self._commands_at_start_resume) +
            self.get_n_command_bytes(self._commands_at_pause_stop) +
            SYSTEM_BYTES_REQUIREMENT +
            self.get_provenance_data_size(self._n_additional_data_items))

        # Return the SDRAM and 1 core
        return ConstantSDRAM(sdram)

    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification)
    def generate_data_specification(self, spec, placement):
        routing_infos = FecDataView.get_routing_infos()
        for mc_key in self._keys_to_partition_id.keys():
            allocated_mc_key = routing_infos.get_first_key_from_pre_vertex(
                self.app_vertex, self._keys_to_partition_id[mc_key])
            if allocated_mc_key != mc_key:
                raise ConfigurationException(
                    f"The command sender {self._label} has requested key "
                    f"{mc_key} for outgoing partition "
                    f"{self._keys_to_partition_id[mc_key]}, but the keys "
                    f"allocated to it ({allocated_mc_key}) do not match. This "
                    "will cause errors in the external devices support and "
                    "therefore needs fixing")

        timed_commands_size = self.get_timed_commands_bytes()
        start_resume_commands_size = self.get_n_command_bytes(
            self._commands_at_start_resume)
        pause_stop_commands_size = self.get_n_command_bytes(
            self._commands_at_pause_stop)

        # reverse memory regions
        self._reserve_memory_regions(
            spec, timed_commands_size, start_resume_commands_size,
            pause_stop_commands_size)

        # Write system region
        spec.comment("\n*** Spec for multicast source ***\n\n")
        spec.switch_write_focus(self.DATA_REGIONS.SYSTEM_REGION)
        spec.write_array(get_simulation_header_array(
            self.get_binary_file_name()))

        # write commands to spec for timed commands
        spec.switch_write_focus(
            region=self.DATA_REGIONS.COMMANDS_WITH_ARBITRARY_TIMES)
        self._write_timed_commands(self._timed_commands, spec)

        # write commands fired off during a start or resume
        spec.switch_write_focus(self.DATA_REGIONS.COMMANDS_AT_START_RESUME)
        self._write_basic_commands(self._commands_at_start_resume, spec)

        # write commands fired off during a pause or end
        spec.switch_write_focus(self.DATA_REGIONS.COMMANDS_AT_STOP_PAUSE)
        self._write_basic_commands(self._commands_at_pause_stop, spec)

        # End-of-Spec:
        spec.end_specification()

    def _write_basic_commands(self, commands, spec):
        """
        :param list(MultiCastCommand) commands:
        :param ~data_specification.DataSpecificationGenerator spec:
        """
        # number of commands
        spec.write_value(len(commands))

        # write commands to region
        for command in commands:
            self.__write_command(command, spec)

    def _write_timed_commands(self, timed_commands, spec):
        """
        :param list(MultiCastCommand) timed_commands:
        :param ~data_specification.DataSpecificationGenerator spec:
        """
        spec.write_value(len(timed_commands))

        # write commands
        for command in timed_commands:
            spec.write_value(command.time)
            self.__write_command(command, spec)

    @classmethod
    def __write_command(cls, command, spec):
        """
        :param MultiCastCommand command:
        :param ~data_specification.DataSpecificationGenerator spec:
        """
        spec.write_value(command.key)
        if command.is_payload:
            spec.write_value(cls._HAS_PAYLOAD)
        else:
            spec.write_value(cls._HAS_NO_PAYLOAD)
        spec.write_value(command.payload if command.is_payload else 0)
        spec.write_value(command.repeat)
        spec.write_value(command.delay_between_repeats)

    def _reserve_memory_regions(
            self, spec, time_command_size, start_command_size,
            end_command_size):
        """
        Reserve SDRAM space for memory areas:

        1. Area for general system information
        2. Area for timed commands
        2. Area for start commands
        3. Area for end commands

        :param ~data_specification.DataSpecificationGenerator spec:
        :param int time_command_size:
        :param int start_command_size:
        :param int end_command_size:
        :param ProvidesProvenanceDataFromMachineImpl vertex:
        """
        spec.comment("\nReserving memory space for data regions:\n\n")

        # Reserve memory:
        spec.reserve_memory_region(
            region=self.DATA_REGIONS.SYSTEM_REGION,
            size=SIMULATION_N_BYTES, label='system')

        spec.reserve_memory_region(
            region=self.DATA_REGIONS.COMMANDS_WITH_ARBITRARY_TIMES,
            size=time_command_size, label='commands with arbitrary times')

        spec.reserve_memory_region(
            region=self.DATA_REGIONS.COMMANDS_AT_START_RESUME,
            size=start_command_size, label='commands with start resume times')

        spec.reserve_memory_region(
            region=self.DATA_REGIONS.COMMANDS_AT_STOP_PAUSE,
            size=end_command_size, label='commands with stop pause times')

        self.reserve_provenance_data_region(spec)

    def get_timed_commands_bytes(self):
        """
        :rtype: int
        """
        n_bytes = self._N_COMMANDS_SIZE
        n_bytes += (
            (self._COMMAND_TIMESTAMP_SIZE + self._COMMAND_WITH_PAYLOAD_SIZE) *
            len(self._timed_commands))
        return n_bytes

    @classmethod
    def get_n_command_bytes(cls, commands):
        """
        :param list(MultiCastCommand) commands:
        :rtype: int
        """
        n_bytes = cls._N_COMMANDS_SIZE
        n_bytes += cls._COMMAND_WITH_PAYLOAD_SIZE * len(commands)
        return n_bytes

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return self.BINARY_FILE_NAME

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ExecutableType.USES_SIMULATION_INTERFACE

    def get_edges_and_partitions(self, pre_vertex, vertex_type, edge_type):
        """
        Construct edges from this vertex to the vertices that this vertex
        knows how to target (and has keys allocated for).

        .. note::
            Do not call this directly from outside either a
            :py:class:`CommandSender` or a
            :py:class:`CommandSenderMachineVertex`.

        :param pre_vertex:
        :type pre_vertex: CommandSender or CommandSenderMachineVertex
        :param type vertex_type:
            subclass of :py:class:`~pacman.model.graphs.AbstractVertex`
        :param type edge_type:
            subclass of :py:class:`~pacman.model.graphs.AbstractEdge`
        :return: edges, partition IDs
        :rtype: tuple(list(~pacman.model.graphs.AbstractEdge), list(str))
        """
        edges = list()
        partition_ids = list()
        keys_added = set()
        for vertex in self._vertex_to_key_map:
            if not isinstance(vertex, vertex_type):
                continue
            for key in self._vertex_to_key_map[vertex]:
                if key not in keys_added:
                    keys_added.add(key)
                    edges.append(edge_type(pre_vertex, vertex))
                    partition_ids.append(self._keys_to_partition_id[key])
        return edges, partition_ids

    def edges_and_partitions(self):
        """
        Construct machine edges from this vertex to the machine vertices
        that this vertex knows how to target (and has keys allocated for).

        :return: edges, partition IDs
        :rtype:
            tuple(list(~pacman.model.graphs.machine.MachineEdge), list(str))
        """
        return self.get_edges_and_partitions(self, MachineVertex, MachineEdge)

    @overrides(ProvidesProvenanceDataFromMachineImpl.
               parse_extra_provenance_items)
    def parse_extra_provenance_items(self, label, x, y, p, provenance_data):
        # pylint: disable=unused-argument
        n_commands_sent, = provenance_data
        with ProvenanceWriter() as db:
            db.insert_core(x, y, p, "Sent_Commands", n_commands_sent)
