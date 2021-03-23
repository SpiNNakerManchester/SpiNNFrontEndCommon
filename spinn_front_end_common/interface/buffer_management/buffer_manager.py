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
from spinn_utilities.log import FormatAdapter
from spinn_utilities.ordered_set import OrderedSet
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.timer import Timer
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
from spinn_front_end_common.utilities.constants import SDP_PORTS
from spinn_front_end_common.utilities.exceptions import (
    BufferableRegionTooSmall, SpinnFrontEndException)
from spinn_front_end_common.utilities.helpful_functions import (
    locate_memory_region_for_placement, locate_extra_monitor_mc_receiver)
from spinn_front_end_common.utilities.globals_variables import get_simulator
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import (BuffersSentDeque, BufferedReceivingData)
from spinn_front_end_common.interface.buffer_management.buffer_models \
    import AbstractReceiveBuffersToHost
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
        # placements object
        "_placements",

        # list of tags
        "_tags",

        # SpiNNMan instance
        "_transceiver",

        # Set of (ip_address, port) that are being listened to for the tags
        "_seen_tags",

        # Set of vertices with buffers to be sent
        "_sender_vertices",

        # Dictionary of sender vertex -> buffers sent
        "_sent_messages",

        # storage area for received data from cores
        "_received_data",

        # Lock to avoid multiple messages being processed at the same time
        "_thread_lock_buffer_out",

        # Lock to avoid multiple messages being processed at the same time
        "_thread_lock_buffer_in",

        # bool flag
        "_finished",

        # listener port
        "_listener_port",

        # the extra monitor cores which support faster data extraction
        "_extra_monitor_cores",

        # the extra_monitor to Ethernet connection map
        "_packet_gather_cores_to_ethernet_connection_map",

        # monitor cores via chip ID
        "_extra_monitor_cores_by_chip",

        # fixed routes, used by the speed up functionality for reports
        "_fixed_routes",

        # machine object
        "_machine",

        # flag for what data extraction to use
        "_uses_advanced_monitors",

        # Support class to help call Java
        "_java_caller"
    ]

    def __init__(self, placements, tags, transceiver, extra_monitor_cores,
                 packet_gather_cores_to_ethernet_connection_map,
                 extra_monitor_to_chip_mapping, machine, fixed_routes,
                 uses_advanced_monitors, report_folder, java_caller=None):
        """
        :param ~pacman.model.placements.Placements placements:
            The placements of the vertices
        :param ~pacman.model.tags.Tags tags: The tags assigned to the vertices
        :param ~spinnman.transceiver.Transceiver transceiver:
            The transceiver to use for sending and receiving information
        :param list(ExtraMonitorSupportMachineVertex) extra_monitor_cores:
            The monitors.
        :param packet_gather_cores_to_ethernet_connection_map:
            mapping of cores to the gatherer vertex placed on them
        :type packet_gather_cores_to_ethernet_connection_map:
            dict(tuple(int,int), DataSpeedUpPacketGatherMachineVertex)
        :param extra_monitor_to_chip_mapping:
        :type extra_monitor_to_chip_mapping:
            dict(tuple(int,int),ExtraMonitorSupportMachineVertex)
        :param ~spinn_machine.Machine machine:
        :param fixed_routes:
        :type fixed_routes: dict(tuple(int,int),~spinn_machine.FixedRouteEntry)
        :param bool uses_advanced_monitors:
        :param str report_folder:
            The directory for reports which includes the file to use as an SQL
            database.
        :param JavaCaller java_caller:
            Support class to call Java, or ``None`` to use Python
        """
        # pylint: disable=too-many-arguments
        self._placements = placements
        self._tags = tags
        self._transceiver = transceiver
        self._extra_monitor_cores = extra_monitor_cores
        self._packet_gather_cores_to_ethernet_connection_map = \
            packet_gather_cores_to_ethernet_connection_map
        self._extra_monitor_cores_by_chip = extra_monitor_to_chip_mapping
        self._fixed_routes = fixed_routes
        self._machine = machine
        self._uses_advanced_monitors = uses_advanced_monitors

        # Set of (ip_address, port) that are being listened to for the tags
        self._seen_tags = set()

        # Set of vertices with buffers to be sent
        self._sender_vertices = set()

        # Dictionary of sender vertex -> buffers sent
        self._sent_messages = dict()

        # storage area for received data from cores
        self._received_data = BufferedReceivingData(report_folder)

        # Lock to avoid multiple messages being processed at the same time
        self._thread_lock_buffer_out = threading.RLock()
        self._thread_lock_buffer_in = threading.RLock()

        self._finished = False
        self._listener_port = None
        self._java_caller = java_caller
        if self._java_caller is not None:
            self._java_caller.set_machine(machine)
            self._java_caller.set_report_folder(report_folder)
            if self._uses_advanced_monitors:
                self._java_caller.set_advanced_monitors(
                    self._placements, self._tags,
                    self._extra_monitor_cores_by_chip,
                    self._packet_gather_cores_to_ethernet_connection_map)

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
        if not self._uses_advanced_monitors:
            return self._transceiver.read_memory(
                placement_x, placement_y, address, length)

        # Round to word boundaries
        initial = address % BYTES_PER_WORD
        address -= initial
        length += initial
        final = (BYTES_PER_WORD - (length % BYTES_PER_WORD)) % BYTES_PER_WORD
        length += final

        sender = self._extra_monitor_cores_by_chip[placement_x, placement_y]
        receiver = locate_extra_monitor_mc_receiver(
            self._machine, placement_x, placement_y,
            self._packet_gather_cores_to_ethernet_connection_map)
        extra_mon_data = receiver.get_data(
            sender, self._placements.get_placement_of_vertex(sender),
            address, length, self._fixed_routes)
        if VERIFY:
            txrx_data = self._transceiver.read_memory(
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
                vertex = self._placements.get_vertex_on_processor(
                    packet.x, packet.y, packet.p)
                if vertex in self._sender_vertices:
                    self._send_messages(
                        packet.space_available, vertex,
                        packet.region_id, packet.sequence_no)

    def _create_connection(self, tag):
        """
        :param ~spinn_machine.tags.IPTag tag:
        :rtype: ~spinnman.connections.udp_packet_connections.EIEIOConnection
        """
        connection = self._transceiver.register_udp_listener(
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
        tags = self._tags.get_ip_tags_for_vertex(vertex)

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

    def add_receiving_vertex(self, vertex):
        """ Add a vertex into the managed list for vertices which require\
            buffers to be received from them during runtime.

        :param AbstractReceiveBuffersToHost vertex: the vertex to be managed
        """
        self._add_buffer_listeners(vertex)

    def add_sender_vertex(self, vertex):
        """ Add a vertex into the managed list for vertices which require\
            buffers to be sent to them during runtime.

        :param AbstractSendsBuffersFromHost vertex: the vertex to be managed
        """
        self._sender_vertices.add(vertex)
        self._add_buffer_listeners(vertex)

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
        self._received_data.reset()

        # rewind buffered in
        for vertex in self._sender_vertices:
            for region in vertex.get_regions():
                vertex.rewind(region)

        self._finished = False

    def resume(self):
        """ Resets any data structures needed before starting running again.
        """

        # update the received data items
        self._received_data.resume()
        self._finished = False

    def clear_recorded_data(self, x, y, p, recording_region_id):
        """ Removes the recorded data stored in memory.

        :param int x: placement x coordinate
        :param int y: placement y coordinate
        :param int p: placement p coordinate
        :param int recording_region_id: the recording region ID
        """
        self._received_data.clear(x, y, p, recording_region_id)

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
        placement = self._placements.get_placement_of_vertex(vertex)
        region_base_address = locate_memory_region_for_placement(
            placement, region, self._transceiver)

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
        self._transceiver.write_memory(
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

        placement = self._placements.get_placement_of_vertex(vertex)
        sdp_header = SDPHeader(
            destination_chip_x=placement.x, destination_chip_y=placement.y,
            destination_cpu=placement.p, flags=SDPFlag.REPLY_NOT_EXPECTED,
            destination_port=SDP_PORTS.INPUT_BUFFERING_SDP_PORT.value)
        sdp_message = SDPMessage(sdp_header, message.bytestring)
        self._transceiver.send_sdp_message(sdp_message)

    def stop(self):
        """ Indicates that the simulation has finished, so no further\
            outstanding requests need to be processed.
        """
        with self._thread_lock_buffer_in:
            with self._thread_lock_buffer_out:
                self._finished = True

    def get_data_for_placements(self, placements, progress=None):
        """
        :param ~pacman.model.placements.Placements placements:
            Where to get the data from.
        :param progress: How to measure/display the progress.
        :type progress: ~spinn_utilities.progress_bar.ProgressBar or None
        """
        if self._java_caller is not None:
            self._java_caller.set_placements(placements, self._transceiver)

        timer = Timer()
        with timer:
            with self._thread_lock_buffer_out:
                if self._java_caller is not None:
                    self._java_caller.get_all_data()
                    if progress:
                        progress.end()
                elif self._uses_advanced_monitors:
                    self.__old_get_data_for_placements_with_monitors(
                        placements, progress)
                else:
                    self.__old_get_data_for_placements(placements, progress)
        get_simulator().add_extraction_timing(timer.measured_interval)

    def __old_get_data_for_placements_with_monitors(
            self, placements, progress):
        """
        :param ~pacman.model.placements.Placements placements:
            Where to get the data from.
        :param progress: How to measure/display the progress.
        :type progress: ~spinn_utilities.progress_bar.ProgressBar or None
        """
        # locate receivers
        receivers = list(OrderedSet(
            locate_extra_monitor_mc_receiver(
                self._machine, placement.x, placement.y,
                self._packet_gather_cores_to_ethernet_connection_map)
            for placement in placements))

        # update transaction id from the machine for all extra monitors
        for extra_mon in self._extra_monitor_cores:
            extra_mon.update_transaction_id_from_machine(self._transceiver)

        # Ugly, to avoid an import loop...
        with receivers[0].streaming(
                receivers, self._transceiver, self._extra_monitor_cores,
                self._placements):
            # get data
            self.__old_get_data_for_placements(placements, progress)

    def __old_get_data_for_placements(self, placements, progress):
        """
        :param ~pacman.model.placements.Placements placements:
            Where to get the data from.
        :param progress: How to measure/display the progress.
        :type progress: ~spinn_utilities.progress_bar.ProgressBar or None
        """
        # get data
        for placement in placements:
            vertex = placement.vertex
            for recording_region_id in vertex.get_recorded_region_ids():
                self._retreive_by_placement(placement, recording_region_id)
                if progress is not None:
                    progress.update()

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
            return self._received_data.get_region_data(
                placement.x, placement.y, placement.p, recording_region_id)

    def _retreive_by_placement(self, placement, region):
        """ Retrieve the data for a vertex; must be locked first.

        :param ~pacman.model.placements.Placement placement:
            the placement to get the data from
        :param int recording_region_id: desired recording data region
        """

        # Has the region information been read
        if not self._received_data.has_region_information(
                placement.x, placement.y, placement.p):

            addr = placement.vertex.get_recording_region_base_address(
                self._transceiver, placement)
            self._get_region_information(
                addr, placement.x, placement.y, placement.p)

        # Read the data if not already received
        if not self._received_data.is_data_from_region_flushed(
                placement.x, placement.y, placement.p, region):

            # Now read the data and store it
            size, addr, missing = self._received_data.get_region_information(
                placement.x, placement.y, placement.p, region)
            data = self._request_data(
                placement.x, placement.y, addr, size)
            self._received_data.store_data_in_region_buffer(
                placement.x, placement.y, placement.p, region, missing, data)

    def _get_region_information(self, addr, x, y, p):
        """ Get the recording information from all regions of a core

        :param addr: The recording region base address
        :param x: The x-coordinate of the chip containing the data
        :param y: The y-coordinate of the chip containing the data
        """
        n_regions = self._transceiver.read_word(x, y, addr)
        n_bytes = get_recording_header_size(n_regions)
        data = self._transceiver.read_memory(
            x, y, addr + BYTES_PER_WORD, n_bytes - BYTES_PER_WORD)
        data_type = _RecordingRegion * n_regions
        regions = data_type.from_buffer_copy(data)
        sizes_and_addresses = [
            (r.size, r.data, bool(r.missing)) for r in regions]
        self._received_data.store_region_information(
            x, y, p, sizes_and_addresses)

    @property
    def sender_vertices(self):
        """ The vertices which are buffered.

        :rtype: iterable(AbstractSendsBuffersFromHost)
        """
        return self._sender_vertices
