# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import math
import struct
import numpy
from enum import IntEnum
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spinnman.messages.eieio import EIEIOPrefix, EIEIOType
from spinnman.messages.eieio.data_messages import EIEIODataHeader
from pacman.executor.injection_decorator import (
    inject_items, supports_injection, inject)
from pacman.model.constraints.key_allocator_constraints import (
    FixedKeyAndMaskConstraint)
from pacman.model.constraints.placer_constraints import BoardConstraint
from pacman.model.resources import (
    CPUCyclesPerTickResource, DTCMResource,
    ReverseIPtagResource, ResourceContainer, VariableSDRAM)
from pacman.model.routing_info import BaseKeyAndMask
from pacman.model.graphs.common import Slice
from pacman.model.graphs.machine import MachineVertex
from spinn_front_end_common.utilities.helpful_functions import (
    locate_memory_region_for_placement)
from spinn_front_end_common.interface.buffer_management.buffer_models import (
    SendsBuffersFromHostPreBufferedImpl, AbstractReceiveBuffersToHost)
from spinn_front_end_common.interface.buffer_management.storage_objects\
    .buffered_sending_region import (
        get_n_bytes)
from spinn_front_end_common.utilities import globals_variables
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import (
        BufferedSendingRegion)
from spinn_front_end_common.utilities.constants import (
    SDP_PORTS, SYSTEM_BYTES_REQUIREMENT, SIMULATION_N_BYTES, BYTES_PER_WORD,
    MICRO_TO_MILLISECOND_CONVERSION)
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.abstract_models import (
    AbstractProvidesOutgoingPartitionConstraints,
    AbstractGeneratesDataSpecification, AbstractHasAssociatedBinary,
    AbstractSupportsDatabaseInjection)
from spinn_front_end_common.interface.simulation.simulation_utilities import (
    get_simulation_header_array)
from spinn_front_end_common.interface.provenance import (
    ProvidesProvenanceDataFromMachineImpl)
from spinn_front_end_common.interface.buffer_management.recording_utilities \
    import (get_recording_header_array, get_recording_header_size,
            get_recording_data_constant_size)
from spinn_front_end_common.utilities.utility_objs import (
    ProvenanceDataItem, ExecutableType)

logger = FormatAdapter(logging.getLogger(__name__))

_DEFAULT_MALLOC_REGIONS = 2
_ONE_WORD = struct.Struct("<I")
_TWO_SHORTS = struct.Struct("<HH")

# The microseconds per timestep will be divided by this for the max offset
_MAX_OFFSET_DENOMINATOR = 10


@supports_injection
class ReverseIPTagMulticastSourceMachineVertex(
        MachineVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary, AbstractSupportsDatabaseInjection,
        ProvidesProvenanceDataFromMachineImpl,
        AbstractProvidesOutgoingPartitionConstraints,
        SendsBuffersFromHostPreBufferedImpl, AbstractReceiveBuffersToHost):
    """ A model which allows events to be injected into SpiNNaker and\
        converted in to multicast packets.

    :param str label: The label of this vertex
    :param vertex_slice:
        The slice served via this multicast source
    :type vertex_slice: ~pacman.model.graphs.common.Slice or None
    :param app_vertex:
        The associated application vertex
    :type app_vertex: ReverseIpTagMultiCastSource or None
    :param int n_keys: The number of keys to be sent via this mulitcast source
        (can't be None if vertex_slice is also None)
    :param iterable(~pacman.model.constraints.AbstractConstraint) constraints:
        Any initial constraints to this vertex
    :param str board_address:
        The IP address of the board on which to place this vertex if receiving
        data, either buffered or live (by default, any board is chosen)
    :param int receive_port:
        The port on the board that will listen for incoming event packets
        (default is to disable this feature; set a value to enable it, or set
        the `reserve_reverse_ip_tag parameter` to True if a random port is to
        be used)
    :param int receive_sdp_port:
        The SDP port to listen on for incoming event packets (defaults to 1)
    :param int receive_tag:
        The IP tag to use for receiving live events (uses any by default)
    :param float receive_rate:
    :param int virtual_key:
        The base multicast key to send received events with (assigned
        automatically by default)
    :param int prefix:
        The prefix to "or" with generated multicast keys (default is no prefix)
    :param ~spinnman.messages.eieio.EIEIOPrefix prefix_type:
        Whether the prefix should apply to the upper or lower half of the
        multicast keys (default is upper half)
    :param bool check_keys:
        True if the keys of received events should be verified before sending
        (default False)
    :param ~numpy.ndarray send_buffer_times:
        An array of arrays of time steps at which keys should be sent (one
        array for each key, default disabled)
    :param str send_buffer_partition_id:
        The ID of the partition containing the edges down which the events are
        to be sent
    :param bool reserve_reverse_ip_tag:
        True if the source should set up a tag through which it can receive
        packets; if port is set to None this can be used to enable the
        reception of packets on a randomly assigned port, which can be read
        from the database
    :param bool enable_injection:
        Flag to indicate that data will be received to inject
    """

    class _REGIONS(IntEnum):
        SYSTEM = 0
        CONFIGURATION = 1
        RECORDING = 2
        SEND_BUFFER = 3
        PROVENANCE_REGION = 4

    class _PROVENANCE_ITEMS(IntEnum):
        N_RECEIVED_PACKETS = 0
        N_SENT_PACKETS = 1
        INCORRECT_KEYS = 2
        INCORRECT_PACKETS = 3
        LATE_PACKETS = 4

    # 13 ints (1. has prefix, 2. prefix, 3. prefix type, 4. check key flag,
    #          5. has key, 6. key, 7. mask, 8. buffer space,
    #          9. send buffer flag before notify, 10. tag,
    #          11. tag destination (y, x), 12. receive SDP port,
    #          13. timer offset)
    _CONFIGURATION_REGION_SIZE = 13 * BYTES_PER_WORD

    # Counts to do timer offsets
    _n_vertices = 0
    _n_data_specs = 0

    def __init__(
            self, label,
            vertex_slice=None,
            app_vertex=None,
            n_keys=None,
            constraints=None,

            # General input and output parameters
            board_address=None,

            # Live input parameters
            receive_port=None,
            receive_sdp_port=SDP_PORTS.INPUT_BUFFERING_SDP_PORT.value,
            receive_tag=None,
            receive_rate=10,

            # Key parameters
            virtual_key=None, prefix=None,
            prefix_type=None, check_keys=False,

            # Send buffer parameters
            send_buffer_times=None,
            send_buffer_partition_id=None,

            # Extra flag for receiving packets without a port
            reserve_reverse_ip_tag=False,

            # Flag to indicate that data will be received to inject
            enable_injection=False):
        # pylint: disable=too-many-arguments, too-many-locals
        if vertex_slice is None:
            if n_keys is not None:
                vertex_slice = Slice(0, n_keys - 1)
            else:
                raise KeyError("Either provide a vertex_slice or n_keys")

        super().__init__(label, constraints, app_vertex, vertex_slice)

        self._reverse_iptags = None
        self._n_keys = vertex_slice.n_atoms

        # Set up for receiving live packets
        if receive_port is not None or reserve_reverse_ip_tag:
            self._reverse_iptags = [ReverseIPtagResource(
                port=receive_port, sdp_port=receive_sdp_port,
                tag=receive_tag)]
            if board_address is not None:
                self.add_constraint(BoardConstraint(board_address))
        self._receive_rate = receive_rate
        self._receive_sdp_port = receive_sdp_port

        # Work out if buffers are being sent
        self._send_buffer = None
        self._send_buffer_partition_id = send_buffer_partition_id
        self._send_buffer_size = 0
        n_buffer_times = 0
        if send_buffer_times is not None:
            for i in send_buffer_times:
                if hasattr(i, "__len__"):
                    n_buffer_times += len(i)
                else:
                    # assuming this must be a single integer
                    n_buffer_times += 1
            if n_buffer_times == 0:
                logger.warning(
                    "Combination of send_buffer_times {} and slice {} results "
                    "in a core with a ReverseIPTagMulticastSourceMachineVertex"
                    " which does not spike", send_buffer_times, vertex_slice)
        if n_buffer_times == 0:
            self._send_buffer_times = None
            self._send_buffers = None
        else:
            self._install_send_buffer(send_buffer_times)

        # Set up for recording (if requested)
        self._is_recording = False

        # set flag for checking if in injection mode
        self._in_injection_mode = (
            receive_port is not None or reserve_reverse_ip_tag or
            enable_injection)

        # Sort out the keys to be used
        self._virtual_key = virtual_key
        self._mask = None
        self._prefix = prefix
        self._prefix_type = prefix_type
        self._check_keys = check_keys

        # Work out the prefix details
        if self._prefix is not None:
            if self._prefix_type is None:
                self._prefix_type = EIEIOPrefix.UPPER_HALF_WORD
            if self._prefix_type == EIEIOPrefix.UPPER_HALF_WORD:
                self._prefix = prefix << 16

        # If the user has specified a virtual key
        if self._virtual_key is not None:
            self._install_virtual_key(vertex_slice.n_atoms)

        self._n_vertices += 1

    @staticmethod
    def _max_send_buffer_keys_per_timestep(send_buffer_times, n_keys):
        """
        :param send_buffer_times: When events will be sent
        :type send_buffer_times:
            ~numpy.ndarray(~numpy.ndarray(numpy.int32)) or
            list(~numpy.ndarray(numpy.int32)) or None
        :param int n_keys:
        :rtype: int
        """
        if len(send_buffer_times) and hasattr(send_buffer_times[0], "__len__"):
            counts = numpy.bincount(numpy.concatenate(send_buffer_times))
            if len(counts):
                return max(counts)
            return 0
        if len(send_buffer_times):
            counts = numpy.bincount(send_buffer_times)
            if len(counts):
                return n_keys * max(counts)
            return 0
        return 0

    @classmethod
    def _send_buffer_sdram_per_timestep(cls, send_buffer_times, n_keys):
        """ Determine the amount of SDRAM required per timestep.

        :param send_buffer_times:
        :type send_buffer_times:
            ~numpy.ndarray(~numpy.ndarray(numpy.int32)) or
            list(~numpy.ndarray(numpy.int32)) or None
        :param int n_keys:
        :rtype: int
        """
        # If there is a send buffer, calculate the keys per timestep
        if send_buffer_times is not None:
            return get_n_bytes(cls._max_send_buffer_keys_per_timestep(
                send_buffer_times, n_keys))
        return 0

    @classmethod
    def _recording_sdram_per_timestep(
            cls, machine_time_step, is_recording, receive_rate,
            send_buffer_times, n_keys):
        """
        :param int machine_time_step:
        :param bool is_recording:
        :param float receive_rate:
        :param send_buffer_times:
        :type send_buffer_times:
            ~numpy.ndarray(~numpy.ndarray(numpy.int32)) or
            list(~numpy.ndarray(numpy.int32)) or None
        :param int n_keys:
        :rtype: int
        """
        # If not recording, no SDRAM needed per timestep
        if not is_recording:
            return 0

        # If recording send data, the recorded size is the send size
        if send_buffer_times is not None:
            return cls._send_buffer_sdram_per_timestep(
                send_buffer_times, n_keys)

        # Recording live data, use the user provided receive rate
        keys_per_timestep = math.ceil(
            receive_rate / (
                machine_time_step * MICRO_TO_MILLISECOND_CONVERSION) * 1.1)
        header_size = EIEIODataHeader.get_header_size(
            EIEIOType.KEY_32_BIT, is_payload_base=True)
        # Maximum size is one packet per key
        return ((header_size + EIEIOType.KEY_32_BIT.key_bytes) *
                keys_per_timestep)

    def _install_send_buffer(self, send_buffer_times):
        """
        :param ~numpy.ndarray send_buffer_times:
        """
        if len(send_buffer_times) and hasattr(send_buffer_times[0], "__len__"):
            # Working with a list of lists so check length
            if len(send_buffer_times) != self._n_keys:
                raise ConfigurationException(
                    "The array or arrays of times {} does not have the "
                    "expected length of {}".format(
                        send_buffer_times, self._n_keys))

        self._send_buffer = BufferedSendingRegion()
        self._send_buffer_times = send_buffer_times
        self._send_buffers = {
            self._REGIONS.SEND_BUFFER: self._send_buffer
        }

    def _install_virtual_key(self, n_keys):
        """
        :param int n_keys:
        """
        # check that virtual key is valid
        if self._virtual_key < 0:
            raise ConfigurationException("Virtual keys must be positive")

        # Get a mask and maximum number of keys for the number of keys
        # requested
        self._mask = self._calculate_mask(n_keys)

        if self._prefix is not None:
            # Check that the prefix doesn't change the virtual key in the
            # masked area
            masked_key = (self._virtual_key | self._prefix) & self._mask
            if self._virtual_key != masked_key:
                raise ConfigurationException(
                    "The number of keys, virtual key and key prefix settings "
                    "don't work together")
        else:
            # If no prefix was generated, generate one
            self._prefix_type = EIEIOPrefix.UPPER_HALF_WORD
            self._prefix = self._virtual_key

    @property
    @overrides(ProvidesProvenanceDataFromMachineImpl._provenance_region_id)
    def _provenance_region_id(self):
        return self._REGIONS.PROVENANCE_REGION

    @property
    @overrides(ProvidesProvenanceDataFromMachineImpl._n_additional_data_items)
    def _n_additional_data_items(self):
        return 5

    @property
    @overrides(MachineVertex.resources_required)
    def resources_required(self):
        sim = globals_variables.get_simulator()
        sdram = self.get_sdram_usage(
            self._send_buffer_times, self._is_recording,
            sim.machine_time_step, self._receive_rate, self._n_keys)

        resources = ResourceContainer(
            dtcm=DTCMResource(self.get_dtcm_usage()),
            sdram=sdram,
            cpu_cycles=CPUCyclesPerTickResource(self.get_cpu_usage()),
            reverse_iptags=self._reverse_iptags)
        return resources

    @classmethod
    def get_sdram_usage(
            cls, send_buffer_times, recording_enabled, machine_time_step,
            receive_rate, n_keys):
        """
        :param send_buffer_times: When events will be sent
        :type send_buffer_times:
            ~numpy.ndarray(~numpy.ndarray(numpy.int32)) or
            list(~numpy.ndarray(numpy.int32)) or None
        :param bool recording_enabled: Whether recording is done
        :param int machine_time_step: What the machine timestep is
        :param float receive_rate: What the expected message receive rate is
        :param int n_keys: How many keys are being sent
        :rtype: ~pacman.model.resources.VariableSDRAM
        """
        static_usage = (
            SYSTEM_BYTES_REQUIREMENT +
            cls._CONFIGURATION_REGION_SIZE +
            get_recording_header_size(1) +
            get_recording_data_constant_size(1) +
            cls.get_provenance_data_size(0))
        per_timestep = (
            cls._send_buffer_sdram_per_timestep(send_buffer_times, n_keys) +
            cls._recording_sdram_per_timestep(
                machine_time_step, recording_enabled, receive_rate,
                send_buffer_times, n_keys))
        static_usage += per_timestep
        return VariableSDRAM(static_usage, per_timestep)

    @staticmethod
    def get_dtcm_usage():
        return 1

    @staticmethod
    def get_cpu_usage():
        return 1

    @staticmethod
    def _n_regions_to_allocate(send_buffering, recording):
        """ Get the number of regions that will be allocated

        :param bool send_buffering:
        :param bool recording:
        :rtype: int
        """
        if recording and send_buffering:
            return 5
        elif recording or send_buffering:
            return 4
        return 3

    @property
    def send_buffer_times(self):
        """ When events will be sent.

        :rtype:
            ~numpy.ndarray(~numpy.ndarray(numpy.int32)) or
            list(~numpy.ndarray(numpy.int32)) or None
        """
        return self._send_buffer_times

    @send_buffer_times.setter
    def send_buffer_times(self, send_buffer_times):
        """
        :type send_buffer_times:
            ~numpy.ndarray(~numpy.ndarray(numpy.int32)) or
            list(~numpy.ndarray(numpy.int32)) or None
        """
        self._install_send_buffer(send_buffer_times)

    @staticmethod
    def _is_in_range(
            time_stamp_in_ticks,
            first_machine_time_step, n_machine_time_steps):
        """
        :param int time_stamp_in_ticks:
        :param int first_machine_time_step:
        :param n_machine_time_steps:
        :type n_machine_time_steps: int or None
        """
        return (n_machine_time_steps is None) or (
            first_machine_time_step <= time_stamp_in_ticks <
            n_machine_time_steps)

    def _fill_send_buffer(
            self, first_machine_time_step, run_until_timesteps):
        """ Fill the send buffer with keys to send.

        :param int first_machine_time_step:
        :param int run_until_timesteps:
        """
        key_to_send = self._virtual_key
        if self._virtual_key is None:
            key_to_send = 0

        if self._send_buffer is not None:
            self._send_buffer.clear()
        if (self._send_buffer_times is not None and
                len(self._send_buffer_times)):
            if hasattr(self._send_buffer_times[0], "__len__"):
                # Works with a list-of-lists
                self.__fill_send_buffer_2d(
                    key_to_send, first_machine_time_step, run_until_timesteps)
            else:
                # Work with a single list
                self.__fill_send_buffer_1d(
                    key_to_send, first_machine_time_step, run_until_timesteps)

    def __fill_send_buffer_2d(
            self, key_base, first_time_step, n_time_steps):
        """
        :param int key_base:
        :param int first_time_step:
        :param int n_time_steps:
        """
        for key in range(self._n_keys):
            for tick in sorted(self._send_buffer_times[key]):
                if self._is_in_range(tick, first_time_step, n_time_steps):
                    self._send_buffer.add_key(tick, key_base + key)

    def __fill_send_buffer_1d(
            self, key_base, first_time_step, n_time_steps):
        """
        :param int key_base:
        :param int first_time_step:
        :param int n_time_steps:
        """
        key_list = [key + key_base for key in range(self._n_keys)]
        for tick in sorted(self._send_buffer_times):
            if self._is_in_range(tick, first_time_step, n_time_steps):
                self._send_buffer.add_keys(tick, key_list)

    @staticmethod
    def _generate_prefix(virtual_key, prefix_type):
        """
        :param ~.EIEIOPrefix prefix_type:
        :param int virtual_key:
        :rtype: int
        """
        if prefix_type == EIEIOPrefix.LOWER_HALF_WORD:
            return virtual_key & 0xFFFF
        return (virtual_key >> 16) & 0xFFFF

    @staticmethod
    def _calculate_mask(n_neurons):
        """
        :param int n_neurons:
        :rtype: int
        """
        temp_value = n_neurons.bit_length()
        max_key = 2**temp_value - 1
        mask = 0xFFFFFFFF - max_key
        return mask

    def enable_recording(self, new_state=True):
        """ Enable recording of the keys sent.

        :param bool new_state:
        """
        self._is_recording = new_state

    def _reserve_regions(self, spec, n_machine_time_steps):
        """
        :param ~.DataSpecificationGenerator spec:
        :param int n_machine_time_steps:
        """
        # Reserve system and configuration memory regions:
        spec.reserve_memory_region(
            region=self._REGIONS.SYSTEM,
            size=SIMULATION_N_BYTES, label='SYSTEM')
        spec.reserve_memory_region(
            region=self._REGIONS.CONFIGURATION,
            size=self._CONFIGURATION_REGION_SIZE, label='CONFIGURATION')

        # Reserve recording buffer regions if required
        spec.reserve_memory_region(
            region=self._REGIONS.RECORDING,
            size=get_recording_header_size(1),
            label="RECORDING")

        # Reserve send buffer region if required
        if self._send_buffer_times is not None:
            self._send_buffer_size = (
                self._send_buffer_sdram_per_timestep(
                    self._send_buffer_times, self._n_keys) *
                n_machine_time_steps)
            if self._send_buffer_size:
                spec.reserve_memory_region(
                    region=self._REGIONS.SEND_BUFFER,
                    size=self._send_buffer_size, label="SEND_BUFFER",
                    empty=True)

        self.reserve_provenance_data_region(spec)

    def _update_virtual_key(self, routing_info, machine_graph):
        """
        :param ~pacman.model.routing_info.RoutingInfo routing_info:
        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
        """
        if self._virtual_key is None:
            if self._send_buffer_partition_id is not None:
                rinfo = routing_info.get_routing_info_from_pre_vertex(
                    self, self._send_buffer_partition_id)

                # if no edge leaving this vertex, no key needed
                if rinfo is not None:
                    self._virtual_key = rinfo.first_key
                    self._mask = rinfo.first_mask
            else:
                partitions = machine_graph\
                    .get_multicast_edge_partitions_starting_at_vertex(self)
                partition = next(iter(partitions), None)

                if partition is not None:
                    rinfo = routing_info.get_routing_info_from_partition(
                        partition)
                    self._virtual_key = rinfo.first_key
                    self._mask = rinfo.first_mask

        if self._virtual_key is not None and self._prefix is None:
            self._prefix_type = EIEIOPrefix.UPPER_HALF_WORD
            self._prefix = self._virtual_key

    def _write_configuration(
            self, spec, machine_time_step, time_scale_factor):
        """
        :param ~.DataSpecificationGenerator spec:
        :param int machine_time_step:
        :param int time_scale_factor:
        """
        spec.switch_write_focus(region=self._REGIONS.CONFIGURATION)

        # Write apply_prefix and prefix and prefix_type
        if self._prefix is None:
            spec.write_value(data=0)
            spec.write_value(data=0)
            spec.write_value(data=0)
        else:
            spec.write_value(data=1)
            spec.write_value(data=self._prefix)
            spec.write_value(data=self._prefix_type.value)

        # Write check
        if self._check_keys:
            spec.write_value(data=1)
        else:
            spec.write_value(data=0)

        # Write if you have a key to transmit write it and the mask,
        # otherwise write flags to fill in space
        if self._virtual_key is None:
            spec.write_value(data=0)
            spec.write_value(data=0)
            spec.write_value(data=0)
        else:
            spec.write_value(data=1)
            spec.write_value(data=self._virtual_key)
            spec.write_value(data=self._mask)

        # Write send buffer data
        if self._send_buffer_times is not None:

            spec.write_value(data=self._send_buffer_size)
            # The following disable the buffer notifications
            spec.write_value(data=self._send_buffer_size + 256)
            spec.write_value(data=0)
            spec.write_value(_ONE_WORD.unpack(_TWO_SHORTS.pack(0, 0))[0])
        else:
            spec.write_value(data=0)
            spec.write_value(data=0)
            spec.write_value(data=0)
            spec.write_value(data=0)

        # write SDP port to which SDP packets will be received
        spec.write_value(data=self._receive_sdp_port)

        # write timer offset in microseconds
        max_offset = ((
            machine_time_step * time_scale_factor) // (
            _MAX_OFFSET_DENOMINATOR * 2))
        spec.write_value(
            (int(math.ceil(max_offset / self._n_vertices)) *
             ReverseIPTagMulticastSourceMachineVertex._n_data_specs) +
            int(math.ceil(max_offset)))
        ReverseIPTagMulticastSourceMachineVertex._n_data_specs += 1

    @inject_items({
        "machine_time_step": "MachineTimeStep",
        "time_scale_factor": "TimeScaleFactor",
        "machine_graph": "MemoryMachineGraph",
        "routing_info": "MemoryRoutingInfos",
        "first_machine_time_step": "FirstMachineTimeStep",
        "data_n_time_steps": "DataNTimeSteps",
        "run_until_timesteps": "RunUntilTimeSteps"
    })
    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification,
        additional_arguments={
            "machine_time_step", "time_scale_factor", "machine_graph",
            "routing_info", "first_machine_time_step",
            "data_n_time_steps", "run_until_timesteps"
        })
    def generate_data_specification(
            self, spec, placement,  # @UnusedVariable
            machine_time_step, time_scale_factor, machine_graph, routing_info,
            first_machine_time_step, data_n_time_steps, run_until_timesteps):
        """
        :param int machine_time_step:
        :param int time_scale_factor:
        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
        :param ~pacman.model.routing_info.RoutingInfo routing_info:
        :param int first_machine_time_step:
        :param int data_n_time_steps:
        :param int run_until_timesteps:
        """
        # pylint: disable=too-many-arguments, arguments-differ
        self._update_virtual_key(routing_info, machine_graph)
        self._fill_send_buffer(first_machine_time_step, run_until_timesteps)

        # Reserve regions
        self._reserve_regions(spec, data_n_time_steps)

        # Write the system region
        spec.switch_write_focus(self._REGIONS.SYSTEM)
        spec.write_array(get_simulation_header_array(
            self.get_binary_file_name(), machine_time_step,
            time_scale_factor))

        # Write the additional recording information
        spec.switch_write_focus(self._REGIONS.RECORDING)
        recording_size = 0
        if self._is_recording:
            per_timestep = self._recording_sdram_per_timestep(
                machine_time_step, self._is_recording, self._receive_rate,
                self._send_buffer_times, self._n_keys)
            recording_size = per_timestep * data_n_time_steps
        spec.write_array(get_recording_header_array([recording_size]))

        # Write the configuration information
        self._write_configuration(
            spec, machine_time_step, time_scale_factor)

        # End spec
        spec.end_specification()

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return "reverse_iptag_multicast_source.aplx"

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ExecutableType.USES_SIMULATION_INTERFACE

    @overrides(AbstractProvidesOutgoingPartitionConstraints.
               get_outgoing_partition_constraints)
    def get_outgoing_partition_constraints(self, partition):  # @UnusedVariable
        if self._virtual_key is not None:
            return list([FixedKeyAndMaskConstraint(
                [BaseKeyAndMask(self._virtual_key, self._mask)])])
        return list()

    @property
    def virtual_key(self):
        """
        :rtype: int or None
        """
        return self._virtual_key

    @property
    def mask(self):
        """
        :rtype: int or None
        """
        return self._mask

    @property
    @overrides(AbstractSupportsDatabaseInjection.is_in_injection_mode)
    def is_in_injection_mode(self):
        return self._in_injection_mode

    @inject("FirstMachineTimeStep")
    @inject_items({
        "run_until_timesteps": "RunUntilTimeSteps"
    })
    def update_buffer(
            self, first_machine_time_step, run_until_timesteps):
        """ Updates the buffers on specification of the first machine timestep.
            Note: This is called by injection.

        :param int first_machine_time_step:
            The first machine time step in the simulation
        :param int run_until_timesteps:
            The last machine time step in the simulation
        """
        if self._virtual_key is not None:
            self._fill_send_buffer(
                first_machine_time_step, run_until_timesteps)

    @overrides(AbstractReceiveBuffersToHost.get_recorded_region_ids)
    def get_recorded_region_ids(self):
        if not self._is_recording:
            return []
        return [0]

    @overrides(AbstractReceiveBuffersToHost.get_recording_region_base_address)
    def get_recording_region_base_address(self, txrx, placement):
        return locate_memory_region_for_placement(
            placement, self._REGIONS.RECORDING, txrx)

    @property
    def send_buffers(self):
        """
        :rtype: dict(int,BufferedSendingRegion)
        """
        return self._send_buffers

    @send_buffers.setter
    def send_buffers(self, value):
        self._send_buffers = value

    def get_region_buffer_size(self, region):
        """
        :param int region: Region ID
        :return: Size of buffer, in bytes.
        :rtype: int
        """
        if region == self._REGIONS.SEND_BUFFER:
            return self._send_buffer_size
        return 0

    @overrides(ProvidesProvenanceDataFromMachineImpl.
               get_provenance_data_from_machine)
    def get_provenance_data_from_machine(self, transceiver, placement):
        provenance_data = self._read_provenance_data(transceiver, placement)
        provenance_items = self._read_basic_provenance_items(
            provenance_data, placement)
        provenance_data = self._get_remaining_provenance_data_items(
            provenance_data)
        _, _, _, _, names = self._get_placement_details(placement)

        provenance_items.append(ProvenanceDataItem(
            self._add_name(names, "received_sdp_packets"),
            provenance_data[self._PROVENANCE_ITEMS.N_RECEIVED_PACKETS],
            report=(
                provenance_data[
                    self._PROVENANCE_ITEMS.N_RECEIVED_PACKETS] == 0 and
                self._send_buffer_times is None),
            message=(
                "No SDP packets were received by {}.  If you expected packets"
                " to be injected, this could indicate an error".format(
                    self._label))))
        provenance_items.append(ProvenanceDataItem(
            self._add_name(names, "send_multicast_packets"),
            provenance_data[self._PROVENANCE_ITEMS.N_SENT_PACKETS],
            report=provenance_data[self._PROVENANCE_ITEMS.N_SENT_PACKETS] == 0,
            message=(
                "No multicast packets were sent by {}.  If you expected"
                " packets to be sent this could indicate an error".format(
                    self._label))))
        provenance_items.append(ProvenanceDataItem(
            self._add_name(names, "incorrect_keys"),
            provenance_data[self._PROVENANCE_ITEMS.INCORRECT_KEYS],
            report=provenance_data[self._PROVENANCE_ITEMS.INCORRECT_KEYS] > 0,
            message=(
                "Keys were received by {} that did not match the key {} and"
                " mask {}".format(
                    self._label, self._virtual_key, self._mask))))
        provenance_items.append(ProvenanceDataItem(
            self._add_name(names, "incorrect_packets"),
            provenance_data[self._PROVENANCE_ITEMS.INCORRECT_PACKETS],
            report=provenance_data[
                self._PROVENANCE_ITEMS.INCORRECT_PACKETS] > 0,
            message=(
                "SDP Packets were received by {} that were not correct".format(
                    self._label))))
        provenance_items.append(ProvenanceDataItem(
            self._add_name(names, "late_packets"),
            provenance_data[self._PROVENANCE_ITEMS.LATE_PACKETS],
            report=provenance_data[self._PROVENANCE_ITEMS.LATE_PACKETS] > 0,
            message=(
                "SDP Packets were received by {} that were too late to be"
                " transmitted in the simulation".format(self._label))))

        return provenance_items

    def __repr__(self):
        return self._label
