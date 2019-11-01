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
from concurrent.futures import ThreadPoolExecutor
from six.moves import xrange
from spinn_utilities.log import FormatAdapter
from spinn_utilities.ordered_set import OrderedSet
from spinn_utilities.progress_bar import ProgressBar
from spinnman.constants import UDP_MESSAGE_MAX_SIZE
from spinnman.connections.udp_packet_connections import EIEIOConnection
from spinnman.messages.eieio.command_messages import (
    EIEIOCommandMessage, StopRequests, SpinnakerRequestReadData,
    HostDataReadAck, HostDataRead, SpinnakerRequestBuffers,
    HostSendSequencedData, EventStopRequest)
from spinnman.utilities import utility_functions
from spinnman.messages.sdp import SDPHeader, SDPMessage, SDPFlag
from spinnman.messages.eieio import EIEIOType, create_eieio_command
from spinnman.messages.eieio.data_messages import EIEIODataMessage
from spinn_front_end_common.utilities.constants import (
    SDP_PORTS, BUFFERING_OPERATIONS)
from spinn_front_end_common.utilities.exceptions import (
    BufferableRegionTooSmall, ConfigurationException, SpinnFrontEndException)
from spinn_front_end_common.utilities.helpful_functions import (
    locate_memory_region_for_placement, locate_extra_monitor_mc_receiver)
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import (
        BuffersSentDeque, BufferedReceivingData, ChannelBufferState)
from spinn_front_end_common.interface.buffer_management.buffer_models \
    import (
        AbstractReceiveBuffersToHost)
from .recording_utilities import (
    TRAFFIC_IDENTIFIER, get_last_sequence_number, get_region_pointer)

logger = FormatAdapter(logging.getLogger(__name__))

# The minimum size of any message - this is the headers plus one entry
_MIN_MESSAGE_SIZE = EIEIODataMessage.min_packet_length(
    eieio_type=EIEIOType.KEY_32_BIT, is_timestamp=True)

# The number of bytes in each key to be sent
_N_BYTES_PER_KEY = EIEIOType.KEY_32_BIT.key_bytes  # @UndefinedVariable

_SDP_MAX_PACKAGE_SIZE = 272


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

        # Buffering out thread pool
        "_buffering_out_thread_pool",

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
        :param placements: The placements of the vertices
        :type placements: ~pacman.model.placements.Placements
        :param tags: The tags assigned to the vertices
        :type tags: ~pacman.model.tags.Tags
        :param transceiver: \
            The transceiver to use for sending and receiving information
        :type transceiver: ~spinnman.transceiver.Transceiver
        :param packet_gather_cores_to_ethernet_connection_map:
            mapping of cores to the gatherer vertex placed on them
        :type packet_gather_cores_to_ethernet_connection_map: \
            dict(tuple(int,int),\
            ~spinn_front_end_common.utility_models.DataSpeedUpPacketGatherMachineVertex)
        :param report_folder: The directory for reports which includes the \
            file to use as an SQL database.
        :type report_folder: str
        :param java_caller: Support class to call Java, or None to use python
        :type java_caller:\
            ~spinn_front_end_common.interface.java_caller.JavaCaller
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
        self._buffering_out_thread_pool = ThreadPoolExecutor(max_workers=1)

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

    def _request_data(self, transceiver, placement_x, placement_y, address,
                      length):
        """ Uses the extra monitor cores for data extraction.

        :param transceiver: the spinnman interface
        :type transceiver: :py:class:`spinnman.transceiver.Transceiver`
        :param placement_x: \
            the placement x coord where data is to be extracted from
        :type placement_x: int
        :param placement_y: \
            the placement y coord where data is to be extracted from
        :type placement_y: int
        :param address: the memory address to start at
        :type address: int
        :param length: the number of bytes to extract
        :type length: int
        :return: data as a byte array
        """
        # pylint: disable=too-many-arguments
        if not self._uses_advanced_monitors:
            return transceiver.read_memory(
                placement_x, placement_y, address, length)

        sender = self._extra_monitor_cores_by_chip[placement_x, placement_y]
        receiver = locate_extra_monitor_mc_receiver(
            self._machine, placement_x, placement_y,
            self._packet_gather_cores_to_ethernet_connection_map)
        return receiver.get_data(
            self._placements.get_placement_of_vertex(sender),
            address, length, self._fixed_routes)

    def _receive_buffer_command_message(self, packet):
        """ Handle an EIEIO command message for the buffers.

        :param packet: The EIEIO message received
        :type packet:\
            :py:class:`spinnman.messages.eieio.command_messages.eieio_command_message.EIEIOCommandMessage`
        """
        # pylint: disable=broad-except
        if isinstance(packet, SpinnakerRequestBuffers):
            # noinspection PyBroadException
            try:
                self.__request_buffers(packet)
            except Exception:
                logger.exception("problem when sending messages")
        elif isinstance(packet, SpinnakerRequestReadData):
            try:
                self.__request_read_data(packet)
            except Exception:
                logger.exception("problem when handling data")
        elif isinstance(packet, EIEIOCommandMessage):
            logger.error(
                "The command packet is invalid for buffer management: "
                "command ID {}", packet.eieio_header.command)
        else:
            logger.error(
                "The command packet is invalid for buffer management")

    # Factored out of receive_buffer_command_message to keep code readable
    def __request_buffers(self, packet):
        if not self._finished:
            with self._thread_lock_buffer_in:
                vertex = self._placements.get_vertex_on_processor(
                    packet.x, packet.y, packet.p)
                if vertex in self._sender_vertices:
                    self._send_messages(
                        packet.space_available, vertex,
                        packet.region_id, packet.sequence_no)

    # Factored out of receive_buffer_command_message to keep code readable
    def __request_read_data(self, packet):
        if not self._finished:
            # Send an ACK message to stop the core sending more messages
            ack_message_header = SDPHeader(
                destination_port=(
                    SDP_PORTS.OUTPUT_BUFFERING_SDP_PORT.value),
                destination_cpu=packet.p, destination_chip_x=packet.x,
                destination_chip_y=packet.y,
                flags=SDPFlag.REPLY_NOT_EXPECTED)
            ack_message_data = HostDataReadAck(packet.sequence_no)
            ack_message = SDPMessage(
                ack_message_header, ack_message_data.bytestring)
            self._transceiver.send_sdp_message(ack_message)
        self._buffering_out_thread_pool.submit(
            self._process_buffered_in_packet, packet)

    def _create_connection(self, tag):
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

        :param vertex: the vertex to be managed
        :type vertex:\
            ~spinn_front_end_common.interface.buffer_management.buffer_models.AbstractReceiveBuffersToHost
        """
        self._add_buffer_listeners(vertex)

    def add_sender_vertex(self, vertex):
        """ Add a vertex into the managed list for vertices which require\
            buffers to be sent to them during runtime.

        :param vertex: the vertex to be managed
        :type vertex:\
            ~spinn_front_end_common.interface.buffer_management.buffer_models.AbstractSendsBuffersFromHost
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

        :param x: placement x coordinate
        :type x: int
        :param y: placement y coordinate
        :type y: int
        :param p: placement p coordinate
        :type p: int
        :param recording_region_id: the recording region ID
        :type recording_region_id: int
        """
        self._received_data.clear(x, y, p, recording_region_id)

    def _generate_end_buffering_state_from_machine(
            self, placement, state_region_base_address):

        # retrieve channel state memory area
        channel_state_data = self._request_data(
            transceiver=self._transceiver, placement_x=placement.x,
            address=state_region_base_address, placement_y=placement.y,
            length=ChannelBufferState.size_of_channel_state())
        return ChannelBufferState.create_from_bytearray(channel_state_data)

    def _create_message_to_send(self, size, vertex, region):
        """ Creates a single message to send with the given boundaries.

        :param size: The number of bytes available for the whole packet
        :type size: int
        :param vertex: The vertex to get the keys from
        :type vertex:\
            :py:class:`~spinn_front_end_common.interface.buffer_management.buffer_models.AbstractSendsBuffersFromHost`
        :param region: The region of the vertex to get keys from
        :type region: int
        :return: A new message, or None if no keys can be added
        :rtype: None or\
            :py:class:`~spinnman.messages.eieio.data_messages.EIEIODataMessage`
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

        :param vertex: The vertex to get the keys from
        :type vertex:\
            :py:class:`~spinn_front_end_common.interface.buffer_management.buffer_models.AbstractSendsBuffersFromHost`
        :param region: The region to get the keys from
        :type region: int
        :return: A list of messages
        :rtype: \
            list(:py:class:`~spinnman.messages.eieio.data_messages.EIEIODataMessage`)
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
        """

        # Get the sent messages for the vertex
        if vertex not in self._sent_messages:
            self._sent_messages[vertex] = BuffersSentDeque(region)
        sent_messages = self._sent_messages[vertex]

        # If the sequence number is outside the window, return no messages
        if not sent_messages.update_last_received_sequence_number(sequence_no):
            return list()

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

        :param vertex: The vertex to send to
        :param message: The message to send
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
        :param placements: Where to get the data from.
        :type placements: ~pacman.model.placements.Placements
        :param progress: How to measure/display the progress.
        :type progress: ~spinn_utilities.progress_bar.ProgressBar or None
        """
        if self._java_caller is not None:
            self._java_caller.set_placements(placements, self._transceiver)

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

    def __old_get_data_for_placements_with_monitors(
            self, placements, progress):
        # locate receivers
        receivers = list(OrderedSet(
            locate_extra_monitor_mc_receiver(
                self._machine, placement.x, placement.y,
                self._packet_gather_cores_to_ethernet_connection_map)
            for placement in placements))

        # Ugly, to avoid an import loop...
        with receivers[0].streaming(
                receivers, self._transceiver, self._extra_monitor_cores,
                self._placements):
            # get data
            self.__old_get_data_for_placements(placements, progress)

    def __old_get_data_for_placements(self, placements, progress):
        # get data
        for placement in placements:
            vertex = placement.vertex
            for recording_region_id in vertex.get_recorded_region_ids():
                self._retreive_by_placement(placement, recording_region_id)
                if progress is not None:
                    progress.update()

    def get_data_for_vertex(self, placement, recording_region_id):
        """ It is no longer possible to get access to the data pointer.

        Use get_data_by_vertex instead which returns\
            the data that pointer.read_all() used to return\
            the missing flag as before
        """
        raise NotImplementedError("Use get_data_by_placement instead!.")

    def get_data_by_placement(self, placement, recording_region_id):
        """ Get the data container for all the data retrieved\
            during the simulation from a specific region area of a core.

        :param placement: the placement to get the data from
        :type placement: ~pacman.model.placements.Placement
        :param recording_region_id: desired recording data region
        :type recording_region_id: int
        :return: an array contained all the data received during the\
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
            (byte_array, missing) = self._received_data.get_region_data(
                placement.x, placement.y, placement.p, recording_region_id)
            return byte_array, missing

    def _retreive_by_placement(self, placement, recording_region_id):
        """ Retrieve the data for a vertex; must be locked first.

        :param placement: the placement to get the data from
        :type placement: ~pacman.model.placements.Placement
        :param recording_region_id: desired recording data region
        :type recording_region_id: int
        """
        recording_data_address = \
            placement.vertex.get_recording_region_base_address(
                self._transceiver, placement)

        # Ensure the last sequence number sent has been retrieved
        if not self._received_data.is_end_buffering_sequence_number_stored(
                placement.x, placement.y, placement.p):
            self._received_data.store_end_buffering_sequence_number(
                placement.x, placement.y, placement.p,
                get_last_sequence_number(
                    placement, self._transceiver, recording_data_address))

        # Read the data if not already received
        if not self._received_data.is_data_from_region_flushed(
                placement.x, placement.y, placement.p,
                recording_region_id):

            # Read the end state of the recording for this region
            if not self._received_data.is_end_buffering_state_recovered(
                    placement.x, placement.y, placement.p,
                    recording_region_id):
                end_state = self._generate_end_buffering_state_from_machine(
                    placement, get_region_pointer(
                        placement, self._transceiver, recording_data_address,
                        recording_region_id))
                self._received_data.store_end_buffering_state(
                    placement.x, placement.y, placement.p, recording_region_id,
                    end_state)
            else:
                end_state = self._received_data.get_end_buffering_state(
                    placement.x, placement.y, placement.p, recording_region_id)

            # current read needs to be adjusted in case the last portion of the
            # memory has already been read, but the HostDataRead packet has not
            # been processed by the chip before simulation finished.
            # This situation is identified by the sequence number of the last
            # packet sent to this core and the core internal state of the
            # output buffering finite state machine
            seq_no_last_ack_packet = \
                self._received_data.last_sequence_no_for_core(
                    placement.x, placement.y, placement.p)

            # get the sequence number the core was expecting to see next
            core_next_sequence_number = \
                self._received_data.get_end_buffering_sequence_number(
                    placement.x, placement.y, placement.p)

            # if the core was expecting to see our last sent sequence,
            # it must not have received it
            if core_next_sequence_number == seq_no_last_ack_packet:
                self._process_last_ack(placement, recording_region_id,
                                       end_state)

            # now state is updated, read back values for read pointer and
            # last operation performed
            last_operation = end_state.last_buffer_operation
            start_ptr = end_state.start_address
            end_ptr = end_state.end_address
            write_ptr = end_state.current_write
            read_ptr = end_state.current_read

            # now read_ptr is updated, check memory to read
            if read_ptr < write_ptr:
                length = write_ptr - read_ptr
                logger.debug(
                    "< Reading {} bytes from {}, {}, {}: {} for region {}",
                    length, placement.x, placement.y, placement.p,
                    hex(read_ptr), recording_region_id)
                data = self._request_data(
                    transceiver=self._transceiver, placement_x=placement.x,
                    address=read_ptr, length=length, placement_y=placement.y)
                self._received_data.flushing_data_from_region(
                    placement.x, placement.y, placement.p, recording_region_id,
                    data)

            elif read_ptr > write_ptr:
                length = end_ptr - read_ptr
                if length < 0:
                    raise ConfigurationException(
                        "The amount of data to read is negative!")
                logger.debug(
                    "> Reading {} bytes from {}, {}, {}: {} for region {}",
                    length, placement.x, placement.y, placement.p,
                    hex(read_ptr), recording_region_id)
                data = self._request_data(
                    transceiver=self._transceiver, placement_x=placement.x,
                    address=read_ptr, length=length, placement_y=placement.y)
                self._received_data.store_data_in_region_buffer(
                    placement.x, placement.y, placement.p, recording_region_id,
                    data)
                read_ptr = start_ptr
                length = write_ptr - read_ptr
                logger.debug(
                    "Reading {} bytes from {}, {}, {}: {} for region {}",
                    length, placement.x, placement.y, placement.p,
                    hex(read_ptr), recording_region_id)
                data = self._request_data(
                    transceiver=self._transceiver, placement_x=placement.x,
                    address=read_ptr, length=length, placement_y=placement.y)
                self._received_data.flushing_data_from_region(
                    placement.x, placement.y, placement.p, recording_region_id,
                    data)

            elif (read_ptr == write_ptr and
                    last_operation == BUFFERING_OPERATIONS.BUFFER_WRITE.value):
                length = end_ptr - read_ptr
                logger.debug(
                    "= Reading {} bytes from {}, {}, {}: {} for region {}",
                    length, placement.x, placement.y, placement.p,
                    hex(read_ptr), recording_region_id)
                data = self._request_data(
                    transceiver=self._transceiver, placement_x=placement.x,
                    address=read_ptr, length=length, placement_y=placement.y)
                self._received_data.store_data_in_region_buffer(
                    placement.x, placement.y, placement.p, recording_region_id,
                    data)
                read_ptr = start_ptr
                length = write_ptr - read_ptr
                logger.debug(
                    "Reading {} bytes from {}, {}, {}: {} for region {}",
                    length, placement.x, placement.y, placement.p,
                    hex(read_ptr), recording_region_id)
                data = self._request_data(
                    transceiver=self._transceiver, placement_x=placement.x,
                    address=read_ptr, length=length, placement_y=placement.y)
                self._received_data.flushing_data_from_region(
                    placement.x, placement.y, placement.p, recording_region_id,
                    data)

            elif (read_ptr == write_ptr and
                    last_operation == BUFFERING_OPERATIONS.BUFFER_READ.value):
                data = bytearray()
                self._received_data.flushing_data_from_region(
                    placement.x, placement.y, placement.p, recording_region_id,
                    data)

    def _process_last_ack(self, placement, region_id, end_state):
        # if the last ACK packet has not been processed on the chip,
        # process it now
        last_sent_ack = self._received_data.last_sent_packet_to_core(
            placement.x, placement.y, placement.p)
        last_sent_ack = create_eieio_command.read_eieio_command_message(
            last_sent_ack.data, 0)
        if not isinstance(last_sent_ack, HostDataRead):
            raise Exception(
                "Something somewhere went terribly wrong; looking for a "
                "HostDataRead packet, while I got {0:s}".format(last_sent_ack))

        start_ptr = end_state.start_address
        write_ptr = end_state.current_write
        end_ptr = end_state.end_address
        read_ptr = end_state.current_read

        for i in xrange(last_sent_ack.n_requests):
            in_region = region_id == last_sent_ack.region_id(i)
            if in_region and not end_state.is_state_updated:
                read_ptr += last_sent_ack.space_read(i)
                if (read_ptr == write_ptr or
                        (read_ptr == end_ptr and write_ptr == start_ptr)):
                    end_state.update_last_operation(
                        BUFFERING_OPERATIONS.BUFFER_READ.value)
                if read_ptr == end_ptr:
                    read_ptr = start_ptr
                elif read_ptr > end_ptr:
                    raise Exception(
                        "Something somewhere went terribly wrong; I was "
                        "reading beyond the region area")
        end_state.update_read_pointer(read_ptr)
        end_state.set_update_completed()

    def _process_buffered_in_packet(self, packet):
        # pylint: disable=broad-except
        logger.debug(
            "received {} read request(s) with sequence: {},"
            " from chip ({},{}, core {}",
            packet.n_requests, packet.sequence_no,
            packet.x, packet.y, packet.p)
        try:
            with self._thread_lock_buffer_out:
                if not self._finished:
                    self._retrieve_and_store_data(packet)
        except Exception:
            logger.warning("problem when handling data", exc_info=True)

    def _retrieve_and_store_data(self, packet):
        """ Following a SpinnakerRequestReadData packet, the data stored\
            during the simulation needs to be read by the host and stored in\
            a data structure, following the specifications of buffering out\
            technique.

        :param packet: \
            SpinnakerRequestReadData packet received from the SpiNNaker system
        :type packet:\
            :py:class:`~spinnman.messages.eieio.command_messages.SpinnakerRequestReadData`
        :rtype: None
        """
        x = packet.x
        y = packet.y
        p = packet.p

        # check packet sequence number
        pkt_seq = packet.sequence_no
        last_pkt_seq = self._received_data.last_sequence_no_for_core(x, y, p)
        next_pkt_seq = (last_pkt_seq + 1) % 256
        if pkt_seq != next_pkt_seq:
            # this sequence number is incorrect
            # re-sent last HostDataRead packet sent
            last_packet_sent = self._received_data.last_sent_packet_to_core(
                x, y, p)
            if last_packet_sent is None:
                raise Exception(
                    "{}, {}, {}: Something somewhere went terribly wrong - "
                    "The packet sequence numbers have gone wrong somewhere: "
                    "the packet sent from the board has incorrect sequence "
                    "number, but the host never sent one acknowledge".format(
                        x, y, p))
            self._transceiver.send_sdp_message(last_packet_sent)
            return

        # read data from memory, store it and create data for return ACK packet
        ack_packet = self._assemble_ack_packet(x, y, p, packet, pkt_seq)

        # create SDP header and message
        return_message = SDPMessage(SDPHeader(
            destination_port=SDP_PORTS.OUTPUT_BUFFERING_SDP_PORT.value,
            destination_cpu=p, destination_chip_x=x, destination_chip_y=y,
            flags=SDPFlag.REPLY_NOT_EXPECTED),
            ack_packet.bytestring)

        # storage of last packet received
        self._received_data.store_last_received_packet_from_core(
            x, y, p, packet)
        self._received_data.update_sequence_no_for_core(x, y, p, pkt_seq)

        # store last sent message and send to the appropriate core
        self._received_data.store_last_sent_packet_to_core(
            x, y, p, return_message)
        self._transceiver.send_sdp_message(return_message)

    def _assemble_ack_packet(self, x, y, p, packet, pkt_seq):
        # pylint: disable=too-many-arguments
        channels = list()
        region_ids = list()
        space_read = list()
        for i in xrange(packet.n_requests):
            length = packet.space_to_be_read(i)
            if not length:
                continue
            start_address = packet.start_address(i)
            region_id = packet.region_id(i)
            channel = packet.channel(i)
            logger.debug(
                "Buffer receive Reading {} bytes from {}, {}, {}:"
                " {} for region {}, channel {}",
                length, x, y, p, hex(start_address), region_id, channel)

            # Note this *always* uses the transceiver, as fast data transfer
            # isn't guaranteed to work whilst a simulation is running!
            self._received_data.store_data_in_region_buffer(
                x, y, p, region_id, self._transceiver.read_memory(
                    x, y, start_address, length))
            channels.append(channel)
            region_ids.append(region_id)
            space_read.append(length)

        # create return acknowledge packet with data stored
        return HostDataRead(
            len(channels), pkt_seq, channels, region_ids, space_read)

    @property
    def sender_vertices(self):
        """ The vertices which are buffered.
        """
        return self._sender_vertices
