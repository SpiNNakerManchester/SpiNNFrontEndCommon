
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
import ctypes
import difflib
import logging
from typing import (
    Dict, Iterable, List, Optional, Set, Tuple, cast, TYPE_CHECKING)
from spinn_utilities.config_holder import get_config_bool
from spinn_utilities.log import FormatAdapter
from spinn_utilities.ordered_set import OrderedSet
from spinn_utilities.progress_bar import ProgressBar
from spinnman.messages.eieio.command_messages import EventStopRequest
from spinnman.messages.eieio import EIEIOType
from spinnman.messages.eieio.data_messages import EIEIODataMessage
from pacman.model.graphs.machine import MachineVertex
from pacman.model.placements import Placement
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.constants import BYTES_PER_WORD
from spinn_front_end_common.utilities.exceptions import (
    SpinnFrontEndException)
from spinn_front_end_common.utilities.helpful_functions import (
    locate_memory_region_for_placement, locate_extra_monitor_mc_receiver)
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import (BuffersSentDeque, BufferDatabase)
from spinn_front_end_common.interface.buffer_management.buffer_models import (
    AbstractReceiveBuffersToHost, AbstractSendsBuffersFromHost,
    AbstractReceiveRegionsToHost)
from spinn_front_end_common.utilities.exceptions import (
    BufferedRegionNotPresent)
from spinn_front_end_common.utility_models.streaming_context_manager import (
    StreamingContextManager)
from .recording_utilities import get_recording_header_size
if TYPE_CHECKING:
    from spinn_front_end_common.interface.java_caller import JavaCaller


logger = FormatAdapter(logging.getLogger(__name__))

# The minimum size of any message - this is the headers plus one entry
_MIN_MESSAGE_SIZE = EIEIODataMessage.min_packet_length(
    eieio_type=EIEIOType.KEY_32_BIT, is_timestamp=True)

# The number of bytes in each key to be sent
_N_BYTES_PER_KEY = EIEIOType.KEY_32_BIT.key_bytes

_SDP_MAX_PACKAGE_SIZE = 272

TRAFFIC_IDENTIFIER = "BufferTraffic"

VERIFY = False


class _RecordingRegion(ctypes.LittleEndianStructure):
    """
    Recording Region data
    """
    _fields_ = [
        # Space available for recording
        ("space", ctypes.c_uint32),
        # The size of the recording region
        ("size", ctypes.c_uint32, 31),
        # Whether any data is missing
        ("missing", ctypes.c_uint32, 1),
        # The address of the data
        ("data", ctypes.c_uint32)
    ]


class BufferManager(object):
    """
    Manager of send buffers.
    """

    __slots__ = (
        "__enable_monitors",

        # Set of vertices with buffers to be sent
        "_sender_vertices",

        # Dictionary of sender vertex -> buffers sent
        "_sent_messages",

        # Support class to help call Java
        "_java_caller",

        # The machine controller, in case it wants to make proxied connections
        # for us
        "_machine_controller")

    def __init__(self) -> None:
        self.__enable_monitors: bool = get_config_bool(
            "Machine", "enable_advanced_monitor_support") or False
        # Set of vertices with buffers to be sent
        self._sender_vertices: Set[AbstractSendsBuffersFromHost] = set()

        # Dictionary of sender vertex -> buffers sent
        self._sent_messages: Dict[
            AbstractSendsBuffersFromHost, BuffersSentDeque] = dict()

        self._java_caller: Optional[JavaCaller]
        if FecDataView.has_java_caller():
            with BufferDatabase() as db:
                db.write_session_credentials_to_db()
            self._java_caller = FecDataView.get_java_caller()
            if self.__enable_monitors:
                self._java_caller.set_advanced_monitors()
        else:
            self._java_caller = None

        for placement in FecDataView.iterate_placements_by_vertex_type(
                AbstractSendsBuffersFromHost):
            vertex = cast(AbstractSendsBuffersFromHost, placement.vertex)
            if vertex.buffering_input():
                self._sender_vertices.add(vertex)

        with BufferDatabase() as db:
            db.store_setup_data()

    def _request_data(
            self, placement_x: int, placement_y: int, address: int,
            length: int) -> bytes:
        """
        Uses the extra monitor cores for data extraction.

        :param placement_x:
            the placement X coordinate where data is to be extracted from
        :param placement_y:
            the placement Y coordinate where data is to be extracted from
        :param address: the memory address to start at
        :param length: the number of bytes to extract
        :return: data as a byte array
        """
        if not self.__enable_monitors:
            return FecDataView.read_memory(
                placement_x, placement_y, address, length)

        # Round to word boundaries
        initial = address % BYTES_PER_WORD
        address -= initial
        length += initial
        final = (BYTES_PER_WORD - (length % BYTES_PER_WORD)) % BYTES_PER_WORD
        length += final

        sender = FecDataView.get_monitor_by_xy(placement_x, placement_y)
        receiver = locate_extra_monitor_mc_receiver(placement_x, placement_y)
        extra_mon_data = receiver.get_data(
            sender, FecDataView.get_placement_of_vertex(sender),
            address, length)
        if VERIFY:
            txrx_data = FecDataView.read_memory(
                placement_x, placement_y, address, length)
            self._verify_data(extra_mon_data, txrx_data)

        # If we rounded to word boundaries, strip the padding junk
        if initial and final:
            return extra_mon_data[initial:-final]
        elif initial:
            return extra_mon_data[initial:]
        elif final:
            return extra_mon_data[:-final]
        else:
            return extra_mon_data

    @staticmethod
    def _verify_data(extra_mon_data: bytes, txrx_data: bytes) -> None:
        sm = difflib.SequenceMatcher(a=extra_mon_data, b=txrx_data)
        failed_index = -1
        for (tag, i1, i2, j1, j2) in sm.get_opcodes():
            if tag == 'replace':
                if failed_index < 0:
                    failed_index = i1
                logger.error(
                    "data differs at {}..{}: got {} instead of {}",
                    i1, i2, repr(txrx_data[j1:j2]),
                    repr(extra_mon_data[i1:i2]))
            elif tag == 'insert':
                if failed_index < 0:
                    failed_index = i1
                logger.error(
                    "data differs at {}: extra {}",
                    i1, repr(txrx_data[j1:j2]))
            elif tag == 'delete':
                if failed_index < 0:
                    failed_index = i1
                logger.error(
                    "data differs at {}: lost {}",
                    i1, repr(extra_mon_data[i1:i2]))
        if failed_index >= 0:
            raise ValueError(f"WRONG (at index {failed_index})")

    def load_initial_buffers(self) -> None:
        """
        Load the initial buffers for the senders using memory writes.
        """
        total_data = 0
        for vertex in self._sender_vertices:
            for region in vertex.get_regions():
                total_data += vertex.get_region_buffer_size(region)

        progress = ProgressBar(total_data, "Loading buffers")
        for vertex in self._sender_vertices:
            for region in vertex.get_regions():
                self._send_initial_messages(vertex, region, progress)
        progress.end()

    def reset(self) -> None:
        """
        Resets the buffered regions to start transmitting from the beginning
        of its expected regions and clears the buffered out data files.
        """
        with BufferDatabase() as db:
            db.write_session_credentials_to_db()

        # rewind buffered in
        for vertex in self._sender_vertices:
            for region in vertex.get_regions():
                vertex.rewind(region)

    def resume(self) -> None:
        """
        Resets any data structures needed before starting running again.
        """

    def clear_recorded_data(
            self, x: int, y: int, p: int, recording_region_id: int) -> None:
        """
        Removes the recorded data stored in memory.

        :param x: placement X coordinate
        :param y: placement Y coordinate
        :param p: placement processor ID
        :param recording_region_id: the recording region ID
        """
        with BufferDatabase() as db:
            db.clear_recording_region(x, y, p, recording_region_id)

    def _create_message_to_send(
            self, size: int, vertex: AbstractSendsBuffersFromHost,
            region: int) -> Optional[EIEIODataMessage]:
        """
        Creates a single message to send with the given boundaries.

        :param size: The number of bytes available for the whole packet
        :param vertex: The vertex to get the keys from
        :param region: The region of the vertex to get keys from
        :return: A new message, or `None` if no keys can be added
        """
        # If there are no more messages to send, return None
        if not vertex.is_next_timestamp(region):
            return None

        # Create a new message
        next_timestamp = vertex.get_next_timestamp(region)
        message = EIEIODataMessage.create(
            EIEIOType.KEY_32_BIT, timestamp=next_timestamp)

        # If there is no room for the message, return None
        if message.size + _N_BYTES_PER_KEY > size:
            return None

        # Add keys up to the limit
        bytes_to_go = size - message.size
        while (bytes_to_go >= _N_BYTES_PER_KEY and
                vertex.is_next_key(region, next_timestamp)):
            key = vertex.get_next_key(region)
            message.add_key(key)
            bytes_to_go -= _N_BYTES_PER_KEY

        return message

    def _send_initial_messages(
            self, vertex: AbstractSendsBuffersFromHost, region: int,
            progress: ProgressBar) -> None:
        """
        Send the initial set of messages.

        :param vertex: The vertex to get the keys from
        :param region: The region to get the keys from
        """
        # Get the vertex load details
        # region_base_address = self._locate_region_address(region, vertex)
        placement = FecDataView.get_placement_of_vertex(
            cast(MachineVertex, vertex))
        region_base_address = locate_memory_region_for_placement(
            placement, region)

        # Add packets until out of space
        sent_message = False
        bytes_to_go = vertex.get_region_buffer_size(region)
        if bytes_to_go % 2 != 0:
            raise SpinnFrontEndException(
                f"The buffer region of {vertex} must be divisible by 2")
        all_data = b""
        if vertex.is_empty(region):
            sent_message = True
        else:
            min_size_of_packet = _MIN_MESSAGE_SIZE
            while (vertex.is_next_timestamp(region) and
                    bytes_to_go > min_size_of_packet):
                space_available = min(bytes_to_go, _SDP_MAX_PACKAGE_SIZE)
                next_message = self._create_message_to_send(
                    space_available, vertex, region)
                if next_message is None:
                    break

                # Write the message to the memory
                data = next_message.bytestring
                all_data += data
                sent_message = True

                # Update the positions
                bytes_to_go -= len(data)
                progress.update(len(data))

        if not sent_message:
            raise SpinnFrontEndException(
                f"Unable to create message for {region=} on {vertex=} "
                f"while is_empty reports false.")

        # If there are no more messages and there is space, add a stop request
        if (not vertex.is_next_timestamp(region) and
                bytes_to_go >= EventStopRequest.get_min_packet_length()):
            data = EventStopRequest().bytestring
            # pylint: disable=wrong-spelling-in-comment
            # logger.debug(
            #    "Writing stop message of {} bytes to {} on {}, {}, {}"
            #         len(data), hex(region_base_address),
            #         placement.x, placement.y, placement.p)
            all_data += data
            bytes_to_go -= len(data)
            progress.update(len(data))
            self._sent_messages[vertex] = BuffersSentDeque(
                region, sent_stop_message=True)

        # Do the writing all at once for efficiency
        FecDataView.write_memory(
            placement.x, placement.y, region_base_address, all_data)

    def extract_data(self) -> None:
        """
        Retrieve the data from placed vertices.
        """
        with BufferDatabase() as db:
            db.start_new_extraction()
        if FecDataView.is_last_step():
            recording_placements = list(
                FecDataView.iterate_placements_by_vertex_type(
                    (AbstractReceiveBuffersToHost,
                     AbstractReceiveRegionsToHost)))
        else:
            recording_placements = list(
                FecDataView.iterate_placements_by_vertex_type(
                    AbstractReceiveBuffersToHost))

        if self._java_caller is not None:
            logger.info("Starting buffer extraction using Java")
            self._java_caller.set_placements(recording_placements)
            self._java_caller.extract_all_data()
        elif self.__enable_monitors:
            self.__python_extract_with_monitors(recording_placements)
        else:
            self.__python_extract_no_monitors(recording_placements)

    def __python_extract_with_monitors(
            self, recording_placements: List[Placement]) -> None:
        """
        :param recording_placements: Where to get the data from.
        """
        # locate receivers
        receivers = OrderedSet(
            locate_extra_monitor_mc_receiver(placement.x, placement.y)
            for placement in recording_placements)

        # update transaction id from the machine for all extra monitors
        for extra_mon in FecDataView.iterate_monitors():
            extra_mon.update_transaction_id_from_machine()

        with StreamingContextManager(receivers):
            # get data
            self.__python_extract_no_monitors(recording_placements)

    def __python_extract_no_monitors(
            self, recording_placements: List[Placement]) -> None:
        """
        :param recording_placements: Where to get the data from.
        """
        # get data
        progress = ProgressBar(
            len(recording_placements),
            "Extracting buffers from the last run")

        for placement in progress.over(recording_placements):
            self._retreive_by_placement(placement)

    def get_data_by_placement(self, placement: Placement,
                              recording_region_id: int) -> Tuple[bytes, bool]:
        """
        Deprecated use get_recording or get_download

        :param placement:
        :param recording_region_id:
        :return:
        """
        if isinstance(placement.vertex, AbstractReceiveBuffersToHost):
            if isinstance(placement.vertex, AbstractReceiveRegionsToHost):
                raise SpinnFrontEndException(
                    f"The vertex {placement.vertex} could return "
                    f"either recording or download data")
            logger.warning(
                "get_data_by_placement is deprecated use get_recording")
            return self.get_recording(placement, recording_region_id)

        elif isinstance(placement.vertex, AbstractReceiveRegionsToHost):
            raise SpinnFrontEndException("Use the get_download method")

        else:
            raise NotImplementedError(
                f"Unable to get data for vertex {placement.vertex}")

    def get_recording(self, placement: Placement,
                      recording_region_id: int) -> Tuple[bytes, bool]:
        """
        Get the data container for the data retrieved
        during the simulation from a specific region area of a core.

        Data for all extractions is combined.

        :param placement: The placement to get the data from
        :param recording_region_id: desired recording data region
        :return: an array contained all the data received during the
            simulation, and a flag indicating if any data was missing
        :raises BufferedRegionNotPresent:
            If no data is available nor marked missing.
        :raises NotImplementedError:
            If the placement's vertex is not a type that records data
        """
        try:
            with BufferDatabase() as db:
                return db.get_recording(placement.x, placement.y, placement.p,
                                        recording_region_id)
        except LookupError as lookup_error:
            return self._raise_error(
                placement, recording_region_id, lookup_error)

    def get_download(self, placement: Placement,
                     recording_region_id: int) -> Tuple[bytes, bool]:
        """
        Get the data container for the data retrieved
        during the simulation from a specific region area of a core.

        Only the last data extracted is returned.

        :param placement: the placement to get the data from
        :param recording_region_id: desired recording data region
        :return: an array contained all the data received during the
            simulation, and a flag indicating if any data was missing
        :raises BufferedRegionNotPresent:
            If no data is available nor marked missing.
        :raises NotImplementedError:
            If the placement's vertex is not a type that records data
        """
        try:
            with BufferDatabase() as db:
                return db.get_download_by_extraction_id(
                    placement.x, placement.y, placement.p,
                    recording_region_id, -1)
        except LookupError as lookup_error:
            return self._raise_error(
                placement, recording_region_id, lookup_error)

    def _raise_error(self, placement: Placement, recording_region_id: int,
                     lookup_error: LookupError) -> Tuple[bytes, bool]:
        """
        Raises the correct exception-
        """
        # Ensure that any transfers in progress are complete first
        if not isinstance(placement.vertex, (AbstractReceiveBuffersToHost,
                                             AbstractReceiveRegionsToHost)):
            raise NotImplementedError(
                f"vertex {placement.vertex} does not implement "
                "AbstractReceiveBuffersToHost or AbstractReceiveRegionsToHost "
                "so no data read")

        vertex = placement.vertex
        recording_id_error = False
        region_id_error = False
        if isinstance(vertex, AbstractReceiveBuffersToHost):
            if recording_region_id not in vertex.get_recorded_region_ids():
                recording_id_error = True

        if isinstance(vertex, AbstractReceiveRegionsToHost):
            if recording_region_id not in vertex.get_download_regions(
                    placement):
                region_id_error = True

        if recording_id_error or region_id_error:
            raise BufferedRegionNotPresent(
                    f"{vertex} not set to record or download region "
                    f"{recording_region_id}") from lookup_error
        else:
            raise BufferedRegionNotPresent(
                f"{vertex} should have record region "
                f"{recording_region_id} but there is no data"
            ) from lookup_error

    def _retreive_by_placement(self, placement: Placement) -> None:
        """
        Retrieve the data for a vertex; must be locked first.

        :param placement: the placement to get the data from
        """
        if isinstance(placement.vertex, AbstractReceiveBuffersToHost):
            vertex = cast(AbstractReceiveBuffersToHost, placement.vertex)
            addr = vertex.get_recording_region_base_address(placement)
            sizes_and_addresses = self._get_region_information(
                    addr, placement.x, placement.y)

            # Read the data if not already received
            for region in vertex.get_recorded_region_ids():
                # Now read the data and store it
                size, addr, missing = sizes_and_addresses[region]
                data = self._request_data(
                    placement.x, placement.y, addr, size)
                with BufferDatabase() as db:
                    db.store_recording(placement.x, placement.y, placement.p,
                                       region, missing, data)
        if isinstance(placement.vertex, AbstractReceiveRegionsToHost):
            dl_vtx = cast(AbstractReceiveRegionsToHost, placement.vertex)
            for region, addr, size in dl_vtx.get_download_regions(placement):
                data = self._request_data(placement.x, placement.y, addr, size)
                with BufferDatabase() as db:
                    db.store_download(placement.x, placement.y, placement.p,
                                      region, False, data)

    def _get_region_information(
            self, address: int, x: int, y: int) -> List[Tuple[int, int, bool]]:
        """
        Get the recording information from all regions of a core.

        :param address: The recording region base address
        :param x: The X coordinate of the chip containing the data
        :param y: The Y coordinate of the chip containing the data
        :return: (size, address, missing flag) for each region
        """
        transceiver = FecDataView.get_transceiver()
        n_regions = transceiver.read_word(x, y, address)
        n_bytes = get_recording_header_size(n_regions)
        data = transceiver.read_memory(
            x, y, address + BYTES_PER_WORD, n_bytes - BYTES_PER_WORD)
        data_type = _RecordingRegion * n_regions
        regions = data_type.from_buffer_copy(data)
        sizes_and_addresses = [
            (r.size, r.data, bool(r.missing)) for r in regions]
        return sizes_and_addresses

    @property
    def sender_vertices(self) -> Iterable[AbstractSendsBuffersFromHost]:
        """
        The vertices which are buffered.
        """
        return self._sender_vertices
