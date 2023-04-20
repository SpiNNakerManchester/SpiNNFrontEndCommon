# Copyright (c) 2015 The University of Manchester
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

import logging
import math
import struct
import numpy
from enum import IntEnum
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spinnman.messages.eieio import EIEIOPrefix, EIEIOType
from spinnman.messages.eieio.data_messages import EIEIODataHeader
from pacman.model.resources import ReverseIPtagResource, VariableSDRAM
from pacman.model.graphs.common import Slice
from pacman.model.graphs.machine import MachineVertex
from pacman.utilities.utility_calls import get_field_based_keys
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.helpful_functions import (
    locate_memory_region_for_placement)
from spinn_front_end_common.interface.buffer_management.buffer_models import (
    SendsBuffersFromHostPreBufferedImpl, AbstractReceiveBuffersToHost)
from spinn_front_end_common.interface.buffer_management.storage_objects\
    .buffered_sending_region import (
        get_n_bytes)
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import (
        BufferedSendingRegion)
from spinn_front_end_common.interface.provenance import ProvenanceWriter
from spinn_front_end_common.utilities.constants import (
    SDP_PORTS, SYSTEM_BYTES_REQUIREMENT, SIMULATION_N_BYTES, BYTES_PER_WORD)
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.abstract_models import (
    AbstractGeneratesDataSpecification, AbstractHasAssociatedBinary,
    AbstractSupportsDatabaseInjection)
from spinn_front_end_common.interface.simulation.simulation_utilities import (
    get_simulation_header_array)
from spinn_front_end_common.interface.provenance import (
    ProvidesProvenanceDataFromMachineImpl)
from spinn_front_end_common.interface.buffer_management.recording_utilities \
    import (get_recording_header_array, get_recording_header_size,
            get_recording_data_constant_size)
from spinn_front_end_common.utilities.utility_objs import ExecutableType

logger = FormatAdapter(logging.getLogger(__name__))

_DEFAULT_MALLOC_REGIONS = 2
_ONE_WORD = struct.Struct("<I")
_TWO_SHORTS = struct.Struct("<HH")

# The microseconds per timestep will be divided by this for the max offset
_MAX_OFFSET_DENOMINATOR = 10
# The max offset modulo to stop spikes in simple cases moving to the next ts
_MAX_OFFSET_MODULO = 1000


class ReverseIPTagMulticastSourceMachineVertex(
        MachineVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary, AbstractSupportsDatabaseInjection,
        ProvidesProvenanceDataFromMachineImpl,
        SendsBuffersFromHostPreBufferedImpl, AbstractReceiveBuffersToHost):
    """
    A model which allows events to be injected into SpiNNaker and
    converted in to multicast packets.

    :param str label: The label of this vertex
    :param vertex_slice:
        The slice served via this multicast source
    :type vertex_slice: ~pacman.model.graphs.common.Slice or None
    :param app_vertex:
        The associated application vertex
    :type app_vertex: ReverseIpTagMultiCastSource or None
    :param int n_keys: The number of keys to be sent via this multicast source
        (can't be `None` if vertex_slice is also `None`)
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
        packets; if port is set to `None` this can be used to enable the
        reception of packets on a randomly assigned port, which can be read
        from the database
    :param str injection_partition:
        If not `None`, will enable injection and specify the partition to send
        injected keys with
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

            # Partition to send injection keys with
            injection_partition_id=None):
        # pylint: disable=too-many-arguments
        if vertex_slice is None:
            if n_keys is not None:
                vertex_slice = Slice(0, n_keys - 1)
            else:
                raise KeyError("Either provide a vertex_slice or n_keys")

        if (send_buffer_partition_id is not None and
                injection_partition_id is not None):
            raise ValueError(
                "Can't specify both send_buffer_partition_id and"
                " injection_partition_id")

        super().__init__(label, app_vertex, vertex_slice)

        self._reverse_iptags = []
        self._n_keys = vertex_slice.n_atoms

        # Set up for receiving live packets
        if receive_port is not None or reserve_reverse_ip_tag:
            self._reverse_iptags = [ReverseIPtagResource(
                port=receive_port, sdp_port=receive_sdp_port,
                tag=receive_tag)]
        self._receive_rate = receive_rate
        self._receive_sdp_port = receive_sdp_port

        # Work out if buffers are being sent
        self._send_buffer = None
        self._first_machine_time_step = None
        self._run_until_timesteps = None
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
        self._injection_partition_id = injection_partition_id

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
            counts = numpy.bincount(
                numpy.concatenate(send_buffer_times).astype("int"))
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
        """
        Determine the amount of SDRAM required per timestep.

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
            cls, is_recording, receive_rate, send_buffer_times, n_keys):
        """
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
        # https://github.com/SpiNNakerManchester/SpiNNFrontEndCommon/issues/896
        keys_per_timestep = math.ceil(
            receive_rate / FecDataView.get_simulation_time_step_ms() * 1.1)
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
                    f"The array or arrays of times {send_buffer_times} does "
                    f"not have the expected length of {self._n_keys}")

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
        self._mask = self.calculate_mask(n_keys)

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
    @overrides(MachineVertex.sdram_required)
    def sdram_required(self):
        return self.get_sdram_usage(
            self._send_buffer_times, self._is_recording,
            self._receive_rate, self._n_keys)

    @property
    @overrides(MachineVertex.reverse_iptags)
    def reverse_iptags(self):
        return self._reverse_iptags

    @classmethod
    def get_sdram_usage(
            cls, send_buffer_times, recording_enabled, receive_rate, n_keys):
        """
        :param send_buffer_times: When events will be sent
        :type send_buffer_times:
            ~numpy.ndarray(~numpy.ndarray(numpy.int32)) or
            list(~numpy.ndarray(numpy.int32)) or None
        :param bool recording_enabled: Whether recording is done
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
                recording_enabled, receive_rate, send_buffer_times, n_keys))
        static_usage += per_timestep
        return VariableSDRAM(static_usage, per_timestep)

    @staticmethod
    def _n_regions_to_allocate(send_buffering, recording):
        """
        Get the number of regions that will be allocated

        :param bool send_buffering:
        :param bool recording:
        :rtype: int
        """
        if recording and send_buffering:
            return 5
        if recording or send_buffering:
            return 4
        return 3

    @property
    def send_buffer_times(self):
        """
        When events will be sent.

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
    def _is_in_range(step, first_step, end_step):
        """
        :param int step: The time step to check
        :param int first_step: The smallest support step
        :param int end_step: The step after the end
        :type n_machine_time_steps: int or None
        """
        return end_step is None or (first_step <= step < end_step)

    def _fill_send_buffer(self):
        """
        Fill the send buffer with keys to send.
        """
        first_machine_time_step = FecDataView.get_first_machine_time_step()
        run_until_timesteps = FecDataView.get_current_run_timesteps()
        if (self._first_machine_time_step == first_machine_time_step and
                self._run_until_timesteps == run_until_timesteps):
            return
        self._first_machine_time_step = first_machine_time_step
        self._run_until_timesteps = run_until_timesteps
        key_to_send = self._virtual_key
        if self._virtual_key is None:
            key_to_send = 0

        if self._send_buffer is not None:
            self._send_buffer.clear()
        if (self._send_buffer_times is not None and
                len(self._send_buffer_times)):
            if hasattr(self._send_buffer_times[0], "__len__"):
                # Works with a list-of-lists
                self._fill_send_buffer_2d(key_to_send)
            else:
                # Work with a single list
                self._fill_send_buffer_1d(key_to_send)

    def _fill_send_buffer_2d(self, key_base):
        """
        Add the keys with different times for each atom.
        Can be overridden to override keys.

        :param int key_base: The base key to use
        """
        first_time_step = FecDataView.get_first_machine_time_step()
        end_time_step = FecDataView.get_current_run_timesteps()
        if first_time_step == end_time_step:
            return
        keys = get_field_based_keys(key_base, self._vertex_slice)
        for atom in range(self._vertex_slice.n_atoms):
            for tick in sorted(self._send_buffer_times[atom]):
                if self._is_in_range(tick, first_time_step, end_time_step):
                    self._send_buffer.add_key(tick, keys[atom])

    def _fill_send_buffer_1d(self, key_base):
        """
        Add the keys from the given vertex slice within the given time
        range into the given send buffer, with the same times for each
        atom.  Can be overridden to override keys.

        :param int key_base: The base key to use
        """
        first_time_step = FecDataView.get_first_machine_time_step()
        end_time_step = FecDataView.get_current_run_timesteps()
        if first_time_step == end_time_step:
            return
        keys = get_field_based_keys(key_base, self._vertex_slice)
        key_list = [keys[atom] for atom in range(self._vertex_slice.n_atoms)]
        for tick in sorted(self._send_buffer_times):
            if self._is_in_range(tick, first_time_step, end_time_step):
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
    def calculate_mask(n_neurons):
        """
        :param int n_neurons:
        :rtype: int
        """
        temp_value = n_neurons.bit_length()
        max_key = 2**temp_value - 1
        mask = 0xFFFFFFFF - max_key
        return mask

    def enable_recording(self, new_state=True):
        """
        Enable recording of the keys sent.

        :param bool new_state:
        """
        self._is_recording = new_state

    def _reserve_regions(self, spec):
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
                FecDataView.get_max_run_time_steps())
            if self._send_buffer_size:
                spec.reserve_memory_region(
                    region=self._REGIONS.SEND_BUFFER,
                    size=self._send_buffer_size, label="SEND_BUFFER",
                    empty=True)

        self.reserve_provenance_data_region(spec)

    def update_virtual_key(self):
        routing_info = FecDataView.get_routing_infos()
        if self._virtual_key is None:
            rinfo = None
            if self._send_buffer_partition_id is not None:
                rinfo = routing_info.get_routing_info_from_pre_vertex(
                    self, self._send_buffer_partition_id)
            if self._injection_partition_id is not None:
                rinfo = routing_info.get_routing_info_from_pre_vertex(
                    self, self._injection_partition_id)

            # if no edge leaving this vertex, no key needed
            if rinfo is not None:
                self._virtual_key = rinfo.key
                self._mask = rinfo.mask

        if self._virtual_key is not None and self._prefix is None:
            self._prefix_type = EIEIOPrefix.UPPER_HALF_WORD
            self._prefix = self._virtual_key

    def _write_configuration(self, spec):
        """
        :param ~.DataSpecificationGenerator spec:
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
        max_offset = (FecDataView.get_hardware_time_step_us() // (
            _MAX_OFFSET_DENOMINATOR * 2))
        spec.write_value(
            ((int(math.ceil(max_offset / self._n_vertices)) *
              ReverseIPTagMulticastSourceMachineVertex._n_data_specs) +
             int(math.ceil(max_offset))) % _MAX_OFFSET_MODULO)
        ReverseIPTagMulticastSourceMachineVertex._n_data_specs += 1

    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification,
        additional_arguments={"routing_info"})
    def generate_data_specification(
            self, spec, placement):  # @UnusedVariable
        self.update_virtual_key()

        # Reserve regions
        self._reserve_regions(spec)

        # Write the system region
        spec.switch_write_focus(self._REGIONS.SYSTEM)
        spec.write_array(get_simulation_header_array(
            self.get_binary_file_name()))

        # Write the additional recording information
        spec.switch_write_focus(self._REGIONS.RECORDING)
        recording_size = 0
        if self._is_recording:
            per_timestep = self._recording_sdram_per_timestep(
                self._is_recording, self._receive_rate,
                self._send_buffer_times, self._n_keys)
            recording_size = (
                    per_timestep * FecDataView.get_max_run_time_steps())
        spec.write_array(get_recording_header_array([recording_size]))

        # Write the configuration information
        self._write_configuration(spec)

        # End spec
        spec.end_specification()

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return "reverse_iptag_multicast_source.aplx"

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ExecutableType.USES_SIMULATION_INTERFACE

    def get_virtual_key(self):
        """
        Updates and returns the virtual key. `None` is give a zero value

        :rtype: int or None
        """
        self.update_virtual_key()
        if self._virtual_key:
            return self._virtual_key
        return 0

    @property
    def mask(self):
        """
        :rtype: int or None
        """
        return self._mask

    @property
    @overrides(AbstractSupportsDatabaseInjection.is_in_injection_mode)
    def is_in_injection_mode(self):
        return self._injection_partition_id is not None

    @property
    @overrides(AbstractSupportsDatabaseInjection.injection_partition_id)
    def injection_partition_id(self):
        return self._injection_partition_id

    @overrides(AbstractReceiveBuffersToHost.get_recorded_region_ids)
    def get_recorded_region_ids(self):
        if not self._is_recording:
            return []
        return [0]

    @overrides(AbstractReceiveBuffersToHost.get_recording_region_base_address)
    def get_recording_region_base_address(self, placement):
        return locate_memory_region_for_placement(
            placement, self._REGIONS.RECORDING)

    @property
    def send_buffers(self):
        """
        :rtype: dict(int,BufferedSendingRegion)
        """
        self._fill_send_buffer()
        return self._send_buffers

    @overrides(SendsBuffersFromHostPreBufferedImpl.get_regions)
    def get_regions(self):
        # Avoid update_buffer as not needed and called during reset
        return self._send_buffers.keys()

    @overrides(SendsBuffersFromHostPreBufferedImpl.rewind)
    def rewind(self, region):
        # reset theses so fill send buffer will run when send_buffers called
        self._first_machine_time_step = None
        self._run_until_timesteps = None
        # Avoid update_buffer as not needed and called during reset
        self._send_buffers[region].rewind()

    @overrides(SendsBuffersFromHostPreBufferedImpl.buffering_input)
    def buffering_input(self):
        return self._send_buffers is not None

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

    @overrides(
        ProvidesProvenanceDataFromMachineImpl.parse_extra_provenance_items)
    def parse_extra_provenance_items(self, label, x, y, p, provenance_data):
        n_rcv, n_snt, bad_key, bad_pkt, late = provenance_data

        with ProvenanceWriter() as db:
            db.insert_core(x, y, p, "Received_sdp_packets", n_rcv)
            if n_rcv == 0 and self._send_buffer_times is None:
                db.insert_report(
                    f"No SDP packets were received by {label}. "
                    f"If you expected packets to be injected, "
                    f"this could indicate an error")

            db.insert_core(
                x, y, p, "Send_multicast_packets", n_snt)
            if n_snt == 0:
                db.insert_report(
                    f"No multicast packets were sent by {label}. "
                    f"If you expected packets to be sent "
                    f"this could indicate an error")
            db.insert_core(
                x, y, p, "Incorrect_keys", bad_key)
            if bad_key > 0:
                db.insert_report(
                    f"Keys were received by {label} that did not match the "
                    f"key {self._virtual_key} and mask {self._mask}")

            db.insert_core(x, y, p, "Incorrect_packets", bad_pkt)
            if bad_pkt > 0:
                db.insert_report(
                    f"SDP Packets were received by {label} "
                    f"that were not correct")

            db.insert_core(x, y, p, "Late_packets", late)
            if late > 0:
                db.insert_report(
                    f"SDP Packets were received by {label} that were too "
                    f"late to be transmitted in the simulation")

    def __repr__(self):
        return self._label
