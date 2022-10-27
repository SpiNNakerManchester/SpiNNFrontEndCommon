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
import threading
import ctypes
from spinn_utilities.config_holder import get_config_bool
from spinn_utilities.log import FormatAdapter
from spinn_utilities.ordered_set import OrderedSet
from spinn_utilities.progress_bar import ProgressBar
from spinnman.constants import UDP_MESSAGE_MAX_SIZE
from spinnman.connections.udp_packet_connections import EIEIOConnection
from spinnman.messages.eieio.command_messages import (
    EIEIOCommandMessage, StopRequests, SpinnakerRequestBuffers,
    HostSendSequencedData, EventStopRequest)
from spinnman.utilities import utility_functions
from spinnman.messages.sdp import SDPHeader, SDPMessage, SDPFlag
from spinnman.messages.eieio import EIEIOType
from spinnman.messages.eieio.data_messages import EIEIODataMessage
from data_specification.constants import BYTES_PER_WORD
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.constants import SDP_PORTS
from spinn_front_end_common.utilities.exceptions import (
    BufferableRegionTooSmall, SpinnFrontEndException)
from spinn_front_end_common.utilities.helpful_functions import (
    locate_memory_region_for_placement, locate_extra_monitor_mc_receiver)
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import (BuffersSentDeque)
from spinn_front_end_common.interface.buffer_management.buffer_models \
    import (AbstractReceiveBuffersToHost, AbstractSendsBuffersFromHost)
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import BufferDatabase
from spinn_front_end_common.utility_models.streaming_context_manager import (
    StreamingContextManager)
from .recording_utilities import get_recording_header_size


logger = FormatAdapter(logging.getLogger(__name__))

# The minimum size of any message - this is the headers plus one entry
_MIN_MESSAGE_SIZE = EIEIODataMessage.min_packet_length(
    eieio_type=EIEIOType.KEY_32_BIT, is_timestamp=True)

# The number of bytes in each key to be sent
_N_BYTES_PER_KEY = EIEIOType.KEY_32_BIT.key_bytes  # @UndefinedVariable

_SDP_MAX_PACKAGE_SIZE = 272

TRAFFIC_IDENTIFIER = "BufferTraffic"

VERIFY = False


class _RecordingRegion(ctypes.LittleEndianStructure):
    """ Recording Region data
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
    """ Manager of send buffers.
    """

    __slots__ = [
        # Set of (ip_address, port) that are being listened to for the tags
        "_seen_tags",

        # Set of vertices with buffers to be sent
        "_sender_vertices",

        # Dictionary of sender vertex -> buffers sent
        "_sent_messages",

        # Lock to avoid multiple messages being processed at the same time
        "_thread_lock_buffer_out",

        # Lock to avoid multiple messages being processed at the same time
        "_thread_lock_buffer_in",

        # bool flag
        "_finished",

        # listener port
        "_listener_port",

        # Support class to help call Java
        "_java_caller"
    ]

    def __init__(self):
        # pylint: disable=too-many-arguments
        # Set of (ip_address, port) that are being listened to for the tags
        self._seen_tags = set()

        # Set of vertices with buffers to be sent
        self._sender_vertices = set()

        # Dictionary of sender vertex -> buffers sent
        self._sent_messages = dict()

        # Lock to avoid multiple messages being processed at the same time
        self._thread_lock_buffer_out = threading.RLock()
        self._thread_lock_buffer_in = threading.RLock()

        self._finished = False
        self._listener_port = None

        if FecDataView.has_java_caller():
            self._java_caller = FecDataView.get_java_caller()
            if get_config_bool("Machine", "enable_advanced_monitor_support"):
                self._java_caller.set_advanced_monitors()
        else:
            self._java_caller = None

        for placement in FecDataView.iterate_placements_by_vertex_type(
                (AbstractSendsBuffersFromHost, AbstractReceiveBuffersToHost)):
            vertex = placement.vertex
            if (isinstance(vertex, AbstractSendsBuffersFromHost) and
                    vertex.buffering_input()):
                self._sender_vertices.add(vertex)
            self._add_buffer_listeners(vertex)

            if isinstance(vertex, AbstractReceiveBuffersToHost):
                self._add_buffer_listeners(vertex)

    def _request_data(self, placement_x, placement_y, address, length):
        """ Uses the extra monitor cores for data extraction.

        :param int placement_x:
            the placement x coord where data is to be extracted from
        :param int placement_y:
            the placement y coord where data is to be extracted from
        :param int address: the memory address to start at
        :param int length: the number of bytes to extract
        :return: data as a byte array
        :rtype: bytearray
        """
        # pylint: disable=too-many-arguments
        if not get_config_bool("Machine", "enable_advanced_monitor_support"):
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

    def _verify_data(self, extra_mon_data, txrx_data):
        for index, (extra_mon_element, txrx_element) in enumerate(
                zip(extra_mon_data, txrx_data)):
            if extra_mon_element != txrx_element:
                raise Exception("WRONG (at index {})".format(index))

    def _receive_buffer_command_message(self, packet):
        """ Handle an EIEIO command message for the buffers.

        :param packet: The EIEIO message received
        :type packet:
            ~spinnman.messages.eieio.command_messages.EIEIOCommandMessage
        """
        # pylint: disable=broad-except
        if isinstance(packet, SpinnakerRequestBuffers):
            # noinspection PyBroadException
            try:
                self.__request_buffers(packet)
            except Exception:
                logger.exception("problem when sending messages")
        elif isinstance(packet, EIEIOCommandMessage):
            logger.error(
                "The command packet is invalid for buffer management: "
                "command ID {}", packet.eieio_header.command)
        else:
            logger.error(
                "The command packet is invalid for buffer management")

    # Factored out of receive_buffer_command_message to keep code readable
    def __request_buffers(self, packet):
        """
        :param packet: The EIEIO message received
        :type packet:
            ~spinnman.messages.eieio.command_messages.SpinnakerRequestBuffers
        """
        if not self._finished:
            with self._thread_lock_buffer_in:
                vertex = FecDataView.get_placement_on_processor(
                    packet.x, packet.y, packet.p).vertex
                if vertex in self._sender_vertices:
                    self._send_messages(
                        packet.space_available, vertex,
                        packet.region_id, packet.sequence_no)

    def _create_connection(self, tag):
        """
        :param ~spinn_machine.tags.IPTag tag:
        :rtype: ~spinnman.connections.udp_packet_connections.EIEIOConnection
        """
        connection = FecDataView.get_transceiver().register_udp_listener(
            self._receive_buffer_command_message, EIEIOConnection,
            local_port=tag.port, local_host=tag.ip_address)
        self._seen_tags.add((tag.ip_address, connection.local_port))
        utility_functions.send_port_trigger_message(
            connection, tag.board_address)
        logger.info(
            "Listening for packets using tag {} on {}:{}",
            tag.tag, connection.local_ip_address, connection.local_port)
        return connection

    def _add_buffer_listeners(self, vertex):
        """ Add listeners for buffered data for the given vertex

        :param ~pacman.model.graphs.machine.MachineVertex vertex:
        """

        # Find a tag for receiving buffer data
        tags = FecDataView.get_tags().get_ip_tags_for_vertex(vertex)

        if tags is not None:
            # locate tag associated with the buffer manager traffic
            for tag in tags:
                if tag.traffic_identifier == TRAFFIC_IDENTIFIER:
                    # If the tag port is not assigned create a connection and
                    # assign the port.  Note that this *should* update the
                    # port number in any tags being shared.
                    if tag.port is None:
                        # If connection already setup, ensure subsequent
                        # boards use same listener port in their tag
                        if self._listener_port is None:
                            connection = self._create_connection(tag)
                            tag.port = connection.local_port
                            self._listener_port = connection.local_port
                        else:
                            tag.port = self._listener_port

                    # In case we have tags with different specified ports,
                    # also allow the tag to be created here
                    elif (tag.ip_address, tag.port) not in self._seen_tags:
                        self._create_connection(tag)

    def load_initial_buffers(self):
        """ Load the initial buffers for the senders using memory writes.
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

    def reset(self):
        """ Resets the buffered regions to start transmitting from the\
            beginning of its expected regions and clears the buffered out\
            data files.
        """
        # rewind buffered in
        for vertex in self._sender_vertices:
            for region in vertex.get_regions():
                vertex.rewind(region)

        self._finished = False

    def resume(self):
        """ Resets any data structures needed before starting running again.
        """

        # update the received data items
        self._finished = False

    def clear_recorded_data(self, x, y, p, recording_region_id):
        """ Removes the recorded data stored in memory.

        :param int x: placement x coordinate
        :param int y: placement y coordinate
        :param int p: placement p coordinate
        :param int recording_region_id: the recording region ID
        """
        with BufferDatabase() as db:
            db.clear_region(x, y, p, recording_region_id)

    def _create_message_to_send(self, size, vertex, region):
        """ Creates a single message to send with the given boundaries.

        :param int size: The number of bytes available for the whole packet
        :param AbstractSendsBuffersFromHost vertex:
            The vertex to get the keys from
        :param int region: The region of the vertex to get keys from
        :return: A new message, or None if no keys can be added
        :rtype: None or ~spinnman.messages.eieio.data_messages.EIEIODataMessage
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

    def _send_initial_messages(self, vertex, region, progress):
        """ Send the initial set of messages.

        :param AbstractSendsBuffersFromHost vertex:
            The vertex to get the keys from
        :param int region: The region to get the keys from
        :return: A list of messages
        :rtype: list(~spinnman.messages.eieio.data_messages.EIEIODataMessage)
        """

        # Get the vertex load details
        # region_base_address = self._locate_region_address(region, vertex)
        placement = FecDataView.get_placement_of_vertex(vertex)
        region_base_address = locate_memory_region_for_placement(
            placement, region)

        # Add packets until out of space
        sent_message = False
        bytes_to_go = vertex.get_region_buffer_size(region)
        if bytes_to_go % 2 != 0:
            raise SpinnFrontEndException(
                "The buffer region of {} must be divisible by 2".format(
                    vertex))
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
            raise BufferableRegionTooSmall(
                "The buffer size {} is too small for any data to be added for"
                " region {} of vertex {}".format(bytes_to_go, region, vertex))

        # If there are no more messages and there is space, add a stop request
        if (not vertex.is_next_timestamp(region) and
                bytes_to_go >= EventStopRequest.get_min_packet_length()):
            data = EventStopRequest().bytestring
            # logger.debug(
            #    "Writing stop message of {} bytes to {} on {}, {}, {}".format(
            #         len(data), hex(region_base_address),
            #         placement.x, placement.y, placement.p))
            all_data += data
            bytes_to_go -= len(data)
            progress.update(len(data))
            self._sent_messages[vertex] = BuffersSentDeque(
                region, sent_stop_message=True)

        # Do the writing all at once for efficiency
        FecDataView.write_memory(
            placement.x, placement.y, region_base_address, all_data)

    def _send_messages(self, size, vertex, region, sequence_no):
        """ Send a set of messages.

        :param int size:
        :param AbstractSendsBuffersFromHost vertex:
        :param int region:
        :param int sequence_no:
        """
        # Get the sent messages for the vertex
        if vertex not in self._sent_messages:
            self._sent_messages[vertex] = BuffersSentDeque(region)
        sent_messages = self._sent_messages[vertex]

        # If the sequence number is outside the window, return now with no
        # messages sent
        if not sent_messages.update_last_received_sequence_number(sequence_no):
            return

        # Remote the existing packets from the size available
        bytes_to_go = size
        for message in sent_messages.messages:
            if isinstance(message.eieio_data_message, EIEIODataMessage):
                bytes_to_go -= message.eieio_data_message.size
            else:
                bytes_to_go -= (message.eieio_data_message
                                .get_min_packet_length())

        # Add messages up to the limits
        while (vertex.is_next_timestamp(region) and
                not sent_messages.is_full and bytes_to_go > 0):

            space_available = min(
                bytes_to_go,
                UDP_MESSAGE_MAX_SIZE -
                HostSendSequencedData.get_min_packet_length())
            # logger.debug(
            #     "Bytes to go {}, space available {}".format(
            #         bytes_to_go, space_available))
            next_message = self._create_message_to_send(
                space_available, vertex, region)
            if next_message is None:
                break
            sent_messages.add_message_to_send(next_message)
            bytes_to_go -= next_message.size
            # logger.debug("Adding additional buffer of {} bytes".format(
            #     next_message.size))

        # If the vertex is empty, send the stop messages if there is space
        if (not sent_messages.is_full and
                not vertex.is_next_timestamp(region) and
                bytes_to_go >= EventStopRequest.get_min_packet_length()):
            sent_messages.send_stop_message()

        # If there are no more messages, turn off requests for more messages
        if not vertex.is_next_timestamp(region) and sent_messages.is_empty():
            # logger.debug("Sending stop")
            self._send_request(vertex, StopRequests())

        # Send the messages
        for message in sent_messages.messages:
            # logger.debug("Sending message with sequence {}".format(
            #     message.sequence_no))
            self._send_request(vertex, message)

    def _send_request(self, vertex, message):
        """ Sends a request.

        :param AbstractSendsBuffersFromHost vertex: The vertex to send to
        :param message: The message to send
        :type message:
            ~spinman.messages.eieio.command_messages.EIEIOCommandMessage
        """

        placement = FecDataView.get_placement_of_vertex(vertex)
        sdp_header = SDPHeader(
            destination_chip_x=placement.x, destination_chip_y=placement.y,
            destination_cpu=placement.p, flags=SDPFlag.REPLY_NOT_EXPECTED,
            destination_port=SDP_PORTS.INPUT_BUFFERING_SDP_PORT.value)
        sdp_message = SDPMessage(sdp_header, message.bytestring)
        FecDataView.get_transceiver().send_sdp_message(sdp_message)

    def stop(self):
        """ Indicates that the simulation has finished, so no further\
            outstanding requests need to be processed.
        """
        with self._thread_lock_buffer_in:
            with self._thread_lock_buffer_out:
                self._finished = True

    def __get_recording_placements(self):
        """
        :rtype: list(~.Placement)
        """
        recording_placements = list()
        for placement in FecDataView.iterate_placements_by_vertex_type(
                AbstractReceiveBuffersToHost):
            recording_placements.append(placement)
        return recording_placements

    def get_placement_data(self):
        with self._thread_lock_buffer_out:
            if self._java_caller is not None:
                self.__get_data_for_placements_using_java()
            else:
                recording_placements = self.__get_recording_placements()
                if get_config_bool(
                        "Machine", "enable_advanced_monitor_support"):
                    self.__python_get_data_for_placements_with_monitors(
                        recording_placements)
                else:
                    self.__python_get_data_for_placements(recording_placements)

    def __get_data_for_placements_using_java(self):
        logger.info("Starting buffer extraction using Java")
        self._java_caller.set_placements(
            FecDataView.iterate_placements_by_vertex_type(
                AbstractReceiveBuffersToHost))
        self._java_caller.get_all_data()

    def __python_get_data_for_placements_with_monitors(
            self, recording_placements):
        """
        :param ~pacman.model.placements.Placements recording_placements:
            Where to get the data from.
        """
        # locate receivers
        receivers = list(OrderedSet(
            locate_extra_monitor_mc_receiver(placement.x, placement.y)
            for placement in recording_placements))

        # update transaction id from the machine for all extra monitors
        for extra_mon in FecDataView.iterate_monitors():
            extra_mon.update_transaction_id_from_machine()

        with StreamingContextManager(receivers):
            # get data
            self.__python_get_data_for_placements(recording_placements)

    def __python_get_data_for_placements(self, recording_placements):
        """
        :param ~pacman.model.placements.Placements recording_placements:
            Where to get the data from.
        """
        # get data
        progress = ProgressBar(
            len(recording_placements),
            "Extracting buffers from the last run")

        with BufferDatabase() as db:
            for placement in progress.over(recording_placements):
                self._retreive_by_placement(db, placement)

    def get_data_by_placement(self, placement, recording_region_id):
        """ Get the data container for all the data retrieved\
            during the simulation from a specific region area of a core.

        :param ~pacman.model.placements.Placement placement:
            the placement to get the data from
        :param int recording_region_id: desired recording data region
        :return: an array contained all the data received during the
            simulation, and a flag indicating if any data was missing
        :rtype: tuple(bytearray, bool)
        """
        # Ensure that any transfers in progress are complete first
        if not isinstance(placement.vertex, AbstractReceiveBuffersToHost):
            raise NotImplementedError(
                "vertex {} does not implement AbstractReceiveBuffersToHost "
                "so no data read".format(placement.vertex))
        with self._thread_lock_buffer_out:
            # data flush has been completed - return appropriate data
            with BufferDatabase() as db:
                return db.get_region_data(
                    placement.x, placement.y, placement.p, recording_region_id)

    def _retreive_by_placement(self, db, placement):
        """ Retrieve the data for a vertex; must be locked first.

        :param db BufferDatabase: dtabase to store into
        :param ~pacman.model.placements.Placement placement:
            the placement to get the data from
        :param int recording_region_id: desired recording data region
        """
        vertex = placement.vertex
        addr = vertex.get_recording_region_base_address(placement)
        sizes_and_addresses = self._get_region_information(
                addr, placement.x, placement.y, placement.p)

        # Read the data if not already received
        for region in vertex.get_recorded_region_ids():
            # Now read the data and store it
            size, addr, missing = sizes_and_addresses[region]
            data = self._request_data(
                placement.x, placement.y, addr, size)
            db.store_data_in_region_buffer(
                placement.x, placement.y, placement.p, region, missing, data)

    def _get_region_information(self, addr, x, y, p):
        """ Get the recording information from all regions of a core

        :param addr: The recording region base address
        :param x: The x-coordinate of the chip containing the data
        :param y: The y-coordinate of the chip containing the data
        """
        transceiver = FecDataView.get_transceiver()
        n_regions = transceiver.read_word(x, y, addr)
        n_bytes = get_recording_header_size(n_regions)
        data = transceiver.read_memory(
            x, y, addr + BYTES_PER_WORD, n_bytes - BYTES_PER_WORD)
        data_type = _RecordingRegion * n_regions
        regions = data_type.from_buffer_copy(data)
        sizes_and_addresses = [
            (r.size, r.data, bool(r.missing)) for r in regions]
        return sizes_and_addresses

    @property
    def sender_vertices(self):
        """ The vertices which are buffered.

        :rtype: iterable(AbstractSendsBuffersFromHost)
        """
        return self._sender_vertices
