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

from __future__ import annotations

import sys
from enum import IntEnum
import logging
import math
import struct
from typing import (
    Collection, Dict, Final, List, Optional, Sequence, Union, TYPE_CHECKING)

import numpy
from numpy.typing import NDArray
from typing_extensions import TypeGuard

from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides

from spinnman.messages.eieio import EIEIOPrefix, EIEIOType
from spinnman.messages.eieio.data_messages import EIEIODataHeader
from spinnman.model.enums import ExecutableType

from pacman.model.graphs.common import Slice
from pacman.model.graphs.machine import MachineVertex
from pacman.model.placements import Placement
from pacman.model.resources import (
    ReverseIPtagResource, AbstractSDRAM, VariableSDRAM)
from pacman.utilities.utility_calls import get_keys

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
from spinn_front_end_common.interface.ds import DataSpecificationGenerator
from spinn_front_end_common.interface.provenance import ProvenanceWriter
from spinn_front_end_common.utilities.constants import (
    SYSTEM_BYTES_REQUIREMENT, SIMULATION_N_BYTES, BYTES_PER_WORD)
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

from .eieio_parameters import EIEIOParameters

if TYPE_CHECKING:
    from typing_extensions import TypeAlias
    from .reverse_ip_tag_multi_cast_source import ReverseIpTagMultiCastSource
    _SBT: Final['TypeAlias'] = Union[NDArray, List[NDArray]]
    _SendBufferTimes: TypeAlias = Optional[_SBT]

logger = FormatAdapter(logging.getLogger(__name__))

_DEFAULT_MALLOC_REGIONS = 2
_ONE_WORD = struct.Struct("<I")
_TWO_SHORTS = struct.Struct("<HH")

# The microseconds per timestep will be divided by this for the max offset
_MAX_OFFSET_DENOMINATOR = 10
# The max offset modulo to stop spikes in simple cases
# moving to the next timestep
_MAX_OFFSET_MODULO = 1000


def is_array_list(value: _SendBufferTimes) -> TypeGuard[List[NDArray]]:
    """
    Whether the send buffer times are a list of arrays (i.e., are 2D).
    Ugly, but we'll have the ugly in one place.

    :param value: A collection of send buffer times.
    :return: Whether this is a list of numpy arrays.
    """
    if value is None:
        return False
    return bool(len(value) and hasattr(value[0], "__len__"))


class ReverseIPTagMulticastSourceMachineVertex(
        MachineVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary, AbstractSupportsDatabaseInjection,
        ProvidesProvenanceDataFromMachineImpl,
        SendsBuffersFromHostPreBufferedImpl, AbstractReceiveBuffersToHost):
    """
    A model which allows events to be injected into SpiNNaker and
    converted in to multicast packets.

    :param label: The label of this vertex
    :param vertex_slice:
        The slice served via this multicast source
    :param app_vertex:
        The associated application vertex
    :param n_keys: The number of keys to be sent via this multicast source
        (can't be `None` if vertex_slice is also `None`)
    :param eieio_params:
        General parameters passed from the application vertex.
    :param send_buffer_times:
        An array of arrays of time steps at which keys should be sent (one
        array for each key, default disabled)
    """
    __slots__ = (
        "_reverse_iptags", "_n_keys", "_is_recording",
        "_first_machine_time_step", "_run_until_timesteps",
        "_receive_rate", "_receive_sdp_port",
        "_send_buffer", "_send_buffer_times", "_send_buffers",
        "_send_buffer_size", "_virtual_key", "_mask", "_prefix",
        "_prefix_type", "_check_keys")

    class _Regions(IntEnum):
        SYSTEM = 0
        CONFIGURATION = 1
        RECORDING = 2
        SEND_BUFFER = 3
        PROVENANCE_REGION = 4

    class _ProvenanceItems(IntEnum):
        N_RECEIVED_PACKETS = 0
        N_SENT_PACKETS = 1
        INCORRECT_KEYS = 2
        INCORRECT_PACKETS = 3
        LATE_PACKETS = 4

    # 13 int  (1. has prefix, 2. prefix, 3. prefix type, 4. check key flag,
    #          5. has key, 6. key, 7. mask, 8. buffer space,
    #          9. send buffer flag before notify, 10. tag,
    #          11. tag destination (y, x), 12. receive SDP port,
    #          13. timer offset)
    _CONFIGURATION_REGION_SIZE = 13 * BYTES_PER_WORD

    # Counts to do timer offsets
    _n_vertices: int = 0
    _n_data_specs: int = 0

    def __init__(
            self, label: Optional[str],
            vertex_slice: Optional[Slice] = None,
            app_vertex: Optional[ReverseIpTagMultiCastSource] = None,
            n_keys: Optional[int] = None,
            # General fixed parameters from app vertex
            eieio_params: Optional[EIEIOParameters] = None,
            # Send buffer parameters
            send_buffer_times: _SendBufferTimes = None):
        """

        :param label: The optional name of the vertex
        :param vertex_slice:
            The slice of the application vertex that this machine vertex
            implements.
        :param app_vertex:
            The application vertex that caused this machine vertex to be
            created. If `None`, there is no such application vertex.
        :param n_keys: Number of keys.
            Only used to create a slice if vertex_slice is None.
        :param eieio_params: Parameters to override the defaults
        :param send_buffer_times: Times to spike at
        """
        if vertex_slice is None:
            if n_keys is None:
                raise KeyError("Either provide a vertex_slice or n_keys")
            vertex_slice = Slice(0, n_keys - 1)
        if not eieio_params:
            # Get the defaults
            eieio_params = EIEIOParameters()

        super().__init__(label, app_vertex, vertex_slice)

        self._reverse_iptags: List[ReverseIPtagResource] = []
        self._n_keys = vertex_slice.n_atoms

        # Set up for receiving live packets
        if eieio_params.receive_port is not None or \
                eieio_params.reserve_reverse_ip_tag:
            self._reverse_iptags = [ReverseIPtagResource(
                port=eieio_params.receive_port,
                sdp_port=eieio_params.receive_sdp_port,
                tag=eieio_params.receive_tag)]
        self._receive_rate = eieio_params.receive_rate
        self._receive_sdp_port = eieio_params.receive_sdp_port

        # Work out if buffers are being sent
        self._send_buffer: Optional[BufferedSendingRegion] = None
        self._first_machine_time_step: Optional[int] = None
        self._run_until_timesteps: Optional[int] = None
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
            self._send_buffer_times: _SendBufferTimes = None
            self._send_buffers: Optional[
                Dict[int, BufferedSendingRegion]] = None
        else:
            assert send_buffer_times is not None
            self._install_send_buffer(send_buffer_times)

        # Set up for recording (if requested)
        self._is_recording = False

        # Sort out the keys to be used
        self._virtual_key = eieio_params.virtual_key
        self._mask: Optional[int] = None
        self._prefix = eieio_params.prefix
        self._prefix_type = eieio_params.prefix_type
        self._check_keys = eieio_params.check_keys

        # Work out the prefix details
        if eieio_params.prefix is not None:
            if self._prefix_type is None:
                self._prefix_type = EIEIOPrefix.UPPER_HALF_WORD
            if self._prefix_type == EIEIOPrefix.UPPER_HALF_WORD:
                self._prefix = eieio_params.prefix << 16

        # If the user has specified a virtual key
        if self._virtual_key is not None:
            self._install_virtual_key(vertex_slice.n_atoms)

        ReverseIPTagMulticastSourceMachineVertex._n_vertices += 1

    @staticmethod
    def _max_send_buffer_keys_per_timestep(
            send_buffer_times: _SBT, n_keys: int) -> int:
        """
        :param send_buffer_times: When events will be sent
        :param n_keys:
        """
        if is_array_list(send_buffer_times):
            counts = numpy.bincount(
                numpy.concatenate(send_buffer_times).astype(numpy.uint32))
            if len(counts):
                return int(numpy.max(counts))
            return 0
        if len(send_buffer_times):
            counts = numpy.bincount(send_buffer_times)
            if len(counts):
                return n_keys * int(numpy.max(counts))
            return 0
        return 0

    @classmethod
    def _send_buffer_sdram_per_timestep(
            cls, send_buffer_times: _SendBufferTimes,
            n_keys: int) -> int:
        """
        Determine the amount of SDRAM required per timestep.
        """
        # If there is a send buffer, calculate the keys per timestep
        if send_buffer_times is not None:
            return get_n_bytes(cls._max_send_buffer_keys_per_timestep(
                send_buffer_times, n_keys))
        return 0

    @classmethod
    def _recording_sdram_per_timestep(
            cls, is_recording: bool, receive_rate: float,
            send_buffer_times: _SendBufferTimes, n_keys: int) -> int:
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

    def _install_send_buffer(self, send_buffer_times: _SBT) -> None:
        if is_array_list(send_buffer_times):
            # Working with a list of lists so check length
            if len(send_buffer_times) != self._n_keys:
                raise ConfigurationException(
                    f"The array or arrays of times {send_buffer_times} does "
                    f"not have the expected length of {self._n_keys}")

        self._send_buffer = BufferedSendingRegion()
        self._send_buffer_times = send_buffer_times
        self._send_buffers = {
            self._Regions.SEND_BUFFER: self._send_buffer
        }

    def _clear_send_buffer(self) -> None:
        self._send_buffer = None
        self._send_buffer_times = None
        self._send_buffers = {}

    def _install_virtual_key(self, n_keys: int) -> None:
        assert self._virtual_key is not None
        # check that virtual key is valid
        if self._virtual_key < 0:
            raise ConfigurationException("Virtual keys must be positive")

        # Get a mask and maximum number of keys for the number of keys
        # requested
        self._mask = self.calculate_mask(n_keys)

        if self._prefix is not None:
            # Check that the prefix doesn't change the virtual key in the
            # masked area
            assert self._mask is not None
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
    def _provenance_region_id(self) -> int:
        return self._Regions.PROVENANCE_REGION

    @property
    @overrides(ProvidesProvenanceDataFromMachineImpl._n_additional_data_items)
    def _n_additional_data_items(self) -> int:
        return 5

    @property
    @overrides(MachineVertex.sdram_required)
    def sdram_required(self) -> AbstractSDRAM:
        return self.get_sdram_usage(
            self._send_buffer_times, self._is_recording, self._receive_rate,
            self._n_keys)

    @property
    @overrides(MachineVertex.reverse_iptags)
    def reverse_iptags(self) -> List[ReverseIPtagResource]:
        return self._reverse_iptags

    @classmethod
    def get_sdram_usage(
            cls, send_buffer_times: _SendBufferTimes,
            recording_enabled: bool, receive_rate: float,
            n_keys: int) -> VariableSDRAM:
        """
        :param send_buffer_times: When events will be sent
        :param recording_enabled: Whether recording is done
        :param receive_rate: What the expected message receive rate is
        :param n_keys: How many keys are being sent
        :returns: Variable SDRAM based on the parameters
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
    def _n_regions_to_allocate(send_buffering: bool, recording: bool) -> int:
        """
        Get the number of regions that will be allocated
        """
        if recording and send_buffering:
            return 5
        if recording or send_buffering:
            return 4
        return 3

    @property
    def send_buffer_times(self) -> _SendBufferTimes:
        """
        When events will be sent.
        """
        return self._send_buffer_times

    @send_buffer_times.setter
    def send_buffer_times(self, send_buffer_times: _SendBufferTimes) -> None:
        """
        Set when events will be sent.
        """
        if send_buffer_times is not None:
            self._install_send_buffer(send_buffer_times)
        else:
            self._clear_send_buffer()

    def _fill_send_buffer(self) -> None:
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
        key_to_send = self._virtual_key or 0

        if self._send_buffer is not None:
            self._send_buffer.clear()
        if self._send_buffer_times is not None:
            if is_array_list(self._send_buffer_times):
                # Works with a list-of-lists
                self._fill_send_buffer_2d(key_to_send)
            elif len(self._send_buffer_times):
                # Work with a single list
                self._fill_send_buffer_1d(key_to_send)

    def _fill_send_buffer_2d(self, key_base: int) -> None:
        """
        Add the keys with different times for each atom.
        Can be overridden to override keys.

        :param key_base: The base key to use
        """
        assert self._send_buffer is not None
        assert self._send_buffer_times is not None

        first_time_step = FecDataView.get_first_machine_time_step()
        end_time_step = FecDataView.get_current_run_timesteps() or sys.maxsize
        if first_time_step == end_time_step:
            return
        keys = get_keys(key_base, self.vertex_slice)
        for atom in range(self.vertex_slice.n_atoms):
            for tick in sorted(self._send_buffer_times[atom]):
                if first_time_step <= tick < end_time_step:
                    self._send_buffer.add_key(tick, keys[atom])

    def _fill_send_buffer_1d(self, key_base: int) -> None:
        """
        Add the keys from the given vertex slice within the given time
        range into the given send buffer, with the same times for each
        atom.  Can be overridden to override keys.

        :param key_base: The base key to use
        """
        assert self._send_buffer is not None
        assert self._send_buffer_times is not None

        first_time_step = FecDataView.get_first_machine_time_step()
        end_time_step = FecDataView.get_current_run_timesteps() or sys.maxsize
        if first_time_step == end_time_step:
            return
        keys = get_keys(key_base, self.vertex_slice)
        for tick in sorted(self._send_buffer_times):
            if first_time_step <= tick < end_time_step:
                self._send_buffer.add_keys(tick, keys)

    @staticmethod
    def _generate_prefix(virtual_key: int, prefix_type: EIEIOPrefix) -> int:
        if prefix_type == EIEIOPrefix.LOWER_HALF_WORD:
            return virtual_key & 0xFFFF
        return (virtual_key >> 16) & 0xFFFF

    @staticmethod
    def calculate_mask(n_neurons: int) -> int:
        """
        :param n_neurons:
        :returns:
        """
        temp_value = n_neurons.bit_length()
        max_key = 2**temp_value - 1
        mask = 0xFFFFFFFF - max_key
        return mask

    def enable_recording(self, new_state: bool = True) -> None:
        """
        Enable recording of the keys sent.

        :param new_state:
        """
        self._is_recording = new_state

    def _reserve_regions(self, spec: DataSpecificationGenerator) -> None:
        # Reserve system and configuration memory regions:
        spec.reserve_memory_region(
            region=self._Regions.SYSTEM,
            size=SIMULATION_N_BYTES, label='SYSTEM')
        spec.reserve_memory_region(
            region=self._Regions.CONFIGURATION,
            size=self._CONFIGURATION_REGION_SIZE, label='CONFIGURATION')

        # Reserve recording buffer regions if required
        spec.reserve_memory_region(
            region=self._Regions.RECORDING,
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
                    region=self._Regions.SEND_BUFFER,
                    size=self._send_buffer_size, label="SEND_BUFFER")

        self.reserve_provenance_data_region(spec)

    def update_virtual_key(self) -> None:
        """
        Copy the key from the pre vertex as the virtual key if possible.
        """
        routing_info = FecDataView.get_routing_infos()
        if self._virtual_key is None:
            rinfo = routing_info.get_single_info_from(self)

            # if no edge leaving this vertex, no key needed
            if rinfo is not None:
                self._virtual_key = rinfo.key
                self._mask = rinfo.mask

        if self._virtual_key is not None and self._prefix is None:
            self._prefix_type = EIEIOPrefix.UPPER_HALF_WORD
            self._prefix = self._virtual_key

    def _write_configuration(self, spec: DataSpecificationGenerator) -> None:
        spec.switch_write_focus(region=self._Regions.CONFIGURATION)

        # Write apply_prefix and prefix and prefix_type
        if self._prefix is None:
            spec.write_value(data=0)
            spec.write_value(data=0)
            spec.write_value(data=0)
        else:
            assert self._prefix_type is not None
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
            spec.write_value(data=self._mask or 0)

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
            ((int(math.ceil(
                max_offset /
                ReverseIPTagMulticastSourceMachineVertex._n_vertices)) *
              ReverseIPTagMulticastSourceMachineVertex._n_data_specs) +
             int(math.ceil(max_offset))) % _MAX_OFFSET_MODULO)
        ReverseIPTagMulticastSourceMachineVertex._n_data_specs += 1

    @overrides(AbstractGeneratesDataSpecification.generate_data_specification)
    def generate_data_specification(self, spec: DataSpecificationGenerator,
                                    placement: Placement) -> None:
        self.update_virtual_key()

        # Reserve regions
        self._reserve_regions(spec)

        # Write the system region
        spec.switch_write_focus(self._Regions.SYSTEM)
        spec.write_array(get_simulation_header_array(
            self.get_binary_file_name()))

        # Write the additional recording information
        spec.switch_write_focus(self._Regions.RECORDING)
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
    def get_binary_file_name(self) -> str:
        return "reverse_iptag_multicast_source.aplx"

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self) -> ExecutableType:
        return ExecutableType.USES_SIMULATION_INTERFACE

    def get_virtual_key(self) -> int:
        """
        Updates and returns the virtual key. `None` is give a zero value

        :returns: The key used or 0 if no key used
        """
        self.update_virtual_key()
        if self._virtual_key:
            return self._virtual_key
        return 0

    @property
    def mask(self) -> Optional[int]:
        """
        The mask if calculated
        """
        return self._mask

    @property
    @overrides(AbstractSupportsDatabaseInjection.is_in_injection_mode)
    def is_in_injection_mode(self) -> bool:
        # If the send buffer is not set and there is a virtual key,
        # we are in injection mode (update the key first to ensure it is there)
        # Note: we might be technically in injection mode but have no outgoing
        # edges, and so no key, so we can't send anyway!
        self.update_virtual_key()
        return self._send_buffer is None and self._virtual_key is not None

    @property
    @overrides(AbstractSupportsDatabaseInjection.injection_partition_id)
    def injection_partition_id(self) -> str:
        assert self.is_in_injection_mode
        routing_infos = FecDataView.get_routing_infos()
        parts = routing_infos.get_partitions_from(self)
        # Should be exactly one partition here - verified elsewhere
        return next(iter(parts))

    @overrides(AbstractReceiveBuffersToHost.get_recorded_region_ids)
    def get_recorded_region_ids(self) -> List[int]:
        if not self._is_recording:
            return []
        return [0]

    @overrides(AbstractReceiveBuffersToHost.get_recording_region_base_address)
    def get_recording_region_base_address(self, placement: Placement) -> int:
        return locate_memory_region_for_placement(
            placement, self._Regions.RECORDING)

    @property  # type: ignore[override]
    def send_buffers(self) -> Dict[int, BufferedSendingRegion]:
        """
        Filled send buffers or an empty dict if there are no send buffers
        """
        if self._send_buffers is None:
            return {}
        self._fill_send_buffer()
        return self._send_buffers

    @send_buffers.setter
    def send_buffers(self, value: Dict[int, BufferedSendingRegion]) -> None:
        self._send_buffers = value

    @overrides(SendsBuffersFromHostPreBufferedImpl.get_regions)
    def get_regions(self) -> Collection[int]:
        # Avoid update_buffer as not needed and called during reset
        if self._send_buffers is None:
            return ()
        return self._send_buffers.keys()

    @overrides(SendsBuffersFromHostPreBufferedImpl.rewind)
    def rewind(self, region: int) -> None:
        # reset theses so fill send buffer will run when send_buffers called
        self._first_machine_time_step = None
        self._run_until_timesteps = None
        # Avoid update_buffer as not needed and called during reset
        if self._send_buffers is not None:
            self._send_buffers[region].rewind()

    @overrides(SendsBuffersFromHostPreBufferedImpl.buffering_input)
    def buffering_input(self) -> bool:
        return self._send_buffers is not None

    def get_region_buffer_size(self, region: int) -> int:
        """
        :param region: Region ID
        :return: Size of buffer, in bytes.
        """
        if region == self._Regions.SEND_BUFFER:
            return self._send_buffer_size
        return 0

    @overrides(
        ProvidesProvenanceDataFromMachineImpl.parse_extra_provenance_items)
    def parse_extra_provenance_items(
            self, label: str, x: int, y: int, p: int,
            provenance_data: Sequence[int]) -> None:
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

    def __repr__(self) -> str:
        return self._label or "ReverseIPTagMulticastSourceMachineVertex"
