# spinn_machine imports
from spinn_machine.utilities.progress_bar import ProgressBar

# spinnman imports
from spinnman import constants
from spinnman.connections.udp_packet_connections.udp_eieio_connection import \
    UDPEIEIOConnection
from spinnman.messages.eieio.command_messages.eieio_command_message import \
    EIEIOCommandMessage
from spinnman.messages.eieio.command_messages.stop_requests import StopRequests
from spinnman.utilities import utility_functions
from spinnman.messages.eieio.command_messages.spinnaker_request_read_data \
    import SpinnakerRequestReadData
from spinnman.messages.eieio.command_messages.host_data_read \
    import HostDataRead
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.messages.sdp.sdp_message import SDPMessage
from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.messages.eieio.data_messages.eieio_32bit\
    .eieio_32bit_timed_payload_prefix_data_message\
    import EIEIO32BitTimedPayloadPrefixDataMessage
from spinnman.messages.eieio.eieio_type import EIEIOType
from spinnman.exceptions import SpinnmanInvalidPacketException
from spinnman.messages.eieio.data_messages.eieio_data_message \
    import EIEIODataMessage
from spinnman.messages.eieio.command_messages.spinnaker_request_buffers \
    import SpinnakerRequestBuffers
from spinnman.messages.eieio.command_messages.padding_request\
    import PaddingRequest
from spinnman.messages.eieio.command_messages.host_send_sequenced_data\
    import HostSendSequencedData
from spinnman.messages.eieio.command_messages.event_stop_request \
    import EventStopRequest
from spinnman.messages.eieio import create_eieio_command

# front end common imports
from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.interface.buffer_management.\
    storage_objects.buffers_sent_deque import BuffersSentDeque
from spinn_front_end_common.interface.buffer_management.\
    storage_objects.buffered_receiving_data import BufferedReceivingData
from spinn_front_end_common.utilities import constants as \
    spinn_front_end_constants
from spinn_front_end_common.interface.buffer_management.storage_objects.\
    channel_buffer_state import ChannelBufferState
from spinn_front_end_common.interface.buffer_management \
    import recording_utilities

# general imports
import threading
import logging
import traceback
import os
import re


logger = logging.getLogger(__name__)

# The minimum size of any message - this is the headers plus one entry
_MIN_MESSAGE_SIZE = (EIEIO32BitTimedPayloadPrefixDataMessage
                     .get_min_packet_length())

# The number of bytes in each key to be sent
_N_BYTES_PER_KEY = EIEIOType.KEY_32_BIT.key_bytes  # @UndefinedVariable


class BufferManager(object):
    """ Manager of send buffers
    """

    # Buffer manager traffic type
    TRAFFIC_IDENTIFIER = recording_utilities.TRAFFIC_IDENTIFIER

    __slots__ = [
        # placements object
        "_placements",

        # list of tags
        "_tags",

        # SpiNNMan instance
        "_transceiver",

        # params used for reload purposes
        "_write_reload_files",

        # params used for reload purposes
        "_application_folder_path",

        # params used for reload purposes
        "_reload_buffer_file",

        # params used for reload purposes
        "_reload_buffer_file_paths",

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
        "_finished"
    ]

    def __init__(self, placements, tags, transceiver, write_reload_files,
                 application_folder_path):
        """

        :param placements: The placements of the vertices
        :type placements:\
                    :py:class:`pacman.model.placements.placements.Placements`
        :param tags: The tags assigned to the vertices
        :type tags: :py:class:`pacman.model.tags.tags.Tags`
        :param transceiver: The transceiver to use for sending and receiving\
                    information
        :type transceiver: :py:class:`spinnman.transceiver.Transceiver`
        """

        self._placements = placements
        self._tags = tags
        self._transceiver = transceiver

        # params used for reload purposes
        self._write_reload_files = write_reload_files
        self._application_folder_path = application_folder_path
        self._reload_buffer_file = dict()
        self._reload_buffer_file_paths = dict()

        # Set of (ip_address, port) that are being listened to for the tags
        self._seen_tags = set()

        # Set of vertices with buffers to be sent
        self._sender_vertices = set()

        # Dictionary of sender vertex -> buffers sent
        self._sent_messages = dict()

        # storage area for received data from cores
        self._received_data = BufferedReceivingData()

        # Lock to avoid multiple messages being processed at the same time
        self._thread_lock_buffer_out = threading.Lock()
        self._thread_lock_buffer_in = threading.Lock()

        self._finished = False

    def receive_buffer_command_message(self, packet):
        """ Handle an EIEIO command message for the buffers

        :param packet: The eieio message received
        :type packet:\
                    :py:class:`spinnman.messages.eieio.command_messages.eieio_command_message.EIEIOCommandMessage`
        """
        try:
            if not self._finished:
                if isinstance(packet, SpinnakerRequestBuffers):
                    with self._thread_lock_buffer_in:
                        vertex = self._placements.get_vertex_on_processor(
                            packet.x, packet.y, packet.p)

                        if vertex in self._sender_vertices:

                            # logger.debug(
                            #     "received send request with sequence: {1:d},"
                            #     " space available: {0:d}".format(
                            #         packet.space_available,
                            #         packet.sequence_no))

                            # noinspection PyBroadException
                            try:
                                self._send_messages(
                                    packet.space_available, vertex,
                                    packet.region_id, packet.sequence_no)
                            except Exception:
                                traceback.print_exc()
                elif isinstance(packet, SpinnakerRequestReadData):
                    with self._thread_lock_buffer_out:

                        # logger.debug(
                        #     "received {} read request(s) with sequence: {},"
                        #     " from chip ({},{}, core {}".format(
                        #         packet.n_requests, packet.sequence_no,
                        #         packet.x, packet.y, packet.p))
                        try:
                            self._retrieve_and_store_data(packet)
                        except Exception:
                            traceback.print_exc()
                elif isinstance(packet, EIEIOCommandMessage):
                    raise SpinnmanInvalidPacketException(
                        str(packet.__class__),
                        "The command packet is invalid for buffer management: "
                        "command id {0:d}".format(packet.eieio_header.command))
                else:
                    raise SpinnmanInvalidPacketException(
                        packet.__class__,
                        "The command packet is invalid for buffer management")
        except Exception:
            traceback.print_exc()

    def _create_connection(self, tag):
        if self._transceiver is not None:
            connection = self._transceiver.register_udp_listener(
                self.receive_buffer_command_message, UDPEIEIOConnection,
                local_port=tag.port, local_host=tag.ip_address)
            self._seen_tags.add((tag.ip_address, connection.local_port))
            utility_functions.send_port_trigger_message(
                connection, tag.board_address)
            logger.info(
                "Listening for packets using tag {} on {}:{}".format(
                    tag.tag, connection.local_ip_address,
                    connection.local_port))
            return connection

    def _add_buffer_listeners(self, vertex):
        """ Add listeners for buffered data for the given vertex
        """

        # If using virtual board, no listeners can be set up
        if self._transceiver is None:
            return

        # Find a tag for receiving buffer data
        tags = self._tags.get_ip_tags_for_vertex(vertex)

        if tags is not None:

            # locate the tag that is associated with the buffer manager
            # traffic
            for tag in tags:
                if tag.traffic_identifier == self.TRAFFIC_IDENTIFIER:

                    # If the tag port is not assigned, create a connection and
                    # assign the port.  Note that this *should* update the port
                    # number in any tags being shared
                    if tag.port is None:
                        connection = self._create_connection(tag)
                        tag.port = connection.local_port

                    # In case we have tags with different specified ports, also
                    # allow the tag to be created here
                    elif (tag.ip_address, tag.port) not in self._seen_tags:
                        self._create_connection(tag)

    def add_receiving_vertex(self, vertex):
        """ Add a vertex into the managed list for vertices\
            which require buffers to be received from them during runtime
        """
        self._add_buffer_listeners(vertex)

    def add_sender_vertex(self, vertex):
        """ Add a vertex into the managed list for vertices
            which require buffers to be sent to them during runtime

        :param vertex: the vertex to be managed
        :type vertex:\
                    :py:class:`spinnaker.pyNN.models.abstract_models.buffer_models.abstract_sends_buffers_from_host.AbstractSendsBuffersFromHost`
        """
        self._sender_vertices.add(vertex)
        self._add_buffer_listeners(vertex)

        # if reload script is set up, store the buffers for future usage
        if self._write_reload_files:
            for region in vertex.get_regions():
                filename = "{}_{}".format(
                    re.sub("[\"':]", "_", vertex.label), region)
                file_path = os.path.join(
                    self._application_folder_path, filename)
                self._reload_buffer_file[(vertex, region)] = \
                    open(file_path, "w")
                if vertex not in self._reload_buffer_file_paths:
                    self._reload_buffer_file_paths[vertex] = dict()
                self._reload_buffer_file_paths[vertex][region] = file_path

                # If there is no transceiver, push all the output to the file
                if self._transceiver is None:
                    while vertex.is_next_timestamp(region):
                        next_timestamp = vertex.get_next_timestamp(region)
                        while vertex.is_next_key(region, next_timestamp):
                            key = vertex.get_next_key(region)
                            self._reload_buffer_file[(vertex, region)].write(
                                "{}:{}\n".format(next_timestamp, key))
                    self._reload_buffer_file[(vertex, region)].close()

    def load_initial_buffers(self):
        """ Load the initial buffers for the senders using mem writes
        """
        total_data = 0
        for vertex in self._sender_vertices:
            for region in vertex.get_regions():
                total_data += vertex.get_region_buffer_size(region)

        progress_bar = ProgressBar(
            total_data, "Loading buffers ({} bytes)".format(total_data))
        for vertex in self._sender_vertices:
            for region in vertex.get_regions():
                self._send_initial_messages(vertex, region, progress_bar)
        progress_bar.end()

    def reset(self):
        """ Resets the buffered regions to start transmitting from the\
            beginning of its expected regions and clears the buffered out data\
            files
        """
        # reset buffered out
        self._received_data = BufferedReceivingData()

        # rewind buffered in
        for vertex in self._sender_vertices:
            for region in vertex.get_regions():
                vertex.rewind(region)

    def resume(self):
        """ Resets any data structures needed before starting running again
        """

        # update the received data items
        self._received_data.resume()

    def clear_recorded_data(self, x, y, p, recording_region_id):
        """ Removes the recorded data stored in memory.

        :param x: placement x coord
        :param y: placement y coord
        :param p: placement p coord
        :param recording_region_id: the recording region id

        :return:
        """
        self._received_data.clear(x, y, p, recording_region_id)

    def _generate_end_buffering_state_from_machine(
            self, placement, state_region_base_address):

        # retrieve channel state memory area
        channel_state_data = str(self._transceiver.read_memory(
            placement.x, placement.y, state_region_base_address,
            ChannelBufferState.size_of_channel_state()))
        return ChannelBufferState.create_from_bytearray(channel_state_data)

    def _create_message_to_send(self, size, vertex, region):
        """ Creates a single message to send with the given boundaries.

        :param size: The number of bytes available for the whole packet
        :type size: int
        :param vertex: The vertex to get the keys from
        :type vertex:\
                    :py:class:`spynnaker.pyNN.models.abstract_models.buffer_models.abstract_sends_buffers_from_host.AbstractSendsBuffersFromHost`
        :param region: The region of the vertex to get keys from
        :type region: int
        :return: A new message, or None if no keys can be added
        :rtype: None or\
                    :py:class:`spinnman.messages.eieio.data_messages.eieio_32bit.eieio_32bit_timed_payload_prefix_data_message.EIEIO32BitTimedPayloadPrefixDataMessage`
        """

        # If there are no more messages to send, return None
        if not vertex.is_next_timestamp(region):
            return None

        # Create a new message
        next_timestamp = vertex.get_next_timestamp(region)
        message = EIEIO32BitTimedPayloadPrefixDataMessage(next_timestamp)

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

            if self._write_reload_files:
                self._reload_buffer_file[(vertex, region)].write(
                    "{}:{}\n".format(next_timestamp, key))
        return message

    def _send_initial_messages(self, vertex, region, progress_bar):
        """ Send the initial set of messages

        :param vertex: The vertex to get the keys from
        :type vertex:\
                    :py:class:`spynnaker.pyNN.models.abstract_models.buffer_models.abstract_sends_buffers_from_host.AbstractSendsBuffersFromHost`
        :param region: The region to get the keys from
        :type region: int
        :return: A list of messages
        :rtype: list of\
                    :py:class:`spinnman.messages.eieio.data_messages.eieio_32bit.eieio_32bit_timed_payload_prefix_data_message.EIEIO32BitTimedPayloadPrefixDataMessage`
        """

        # Get the vertex load details
        # region_base_address = self._locate_region_address(region, vertex)
        region_base_address = \
            helpful_functions.locate_memory_region_for_placement(
                self._placements.get_placement_of_vertex(vertex), region,
                self._transceiver)
        placement = self._placements.get_placement_of_vertex(vertex)

        # Add packets until out of space
        sent_message = False
        bytes_to_go = vertex.get_region_buffer_size(region)
        if bytes_to_go % 2 != 0:
            raise exceptions.SpinnFrontEndException(
                "The buffer region of {} must be divisible by 2".format(
                    vertex))
        all_data = ""
        if vertex.is_empty(region):
            sent_message = True
        else:
            min_size_of_packet = \
                EIEIO32BitTimedPayloadPrefixDataMessage.get_min_packet_length()
            while (vertex.is_next_timestamp(region) and
                    bytes_to_go > min_size_of_packet):
                space_available = min(bytes_to_go, 280)
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
                progress_bar.update(len(data))

        if not sent_message:
            raise exceptions.BufferableRegionTooSmall(
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
            progress_bar.update(len(data))
            self._sent_messages[vertex] = BuffersSentDeque(
                region, sent_stop_message=True)

        # If there is any space left, add padding
        if bytes_to_go > 0:
            padding_packet = PaddingRequest()
            n_packets = bytes_to_go / padding_packet.get_min_packet_length()
            data = padding_packet.bytestring
            data *= n_packets
            all_data += data

        # Do the writing all at once for efficiency
        self._transceiver.write_memory(
            placement.x, placement.y, region_base_address, all_data)

    def _send_messages(self, size, vertex, region, sequence_no):
        """ Send a set of messages
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
                constants.UDP_MESSAGE_MAX_SIZE -
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
        """ Sends a request

        :param vertex: The vertex to send to
        :param message: The message to send
        """

        placement = self._placements.get_placement_of_vertex(vertex)
        sdp_header = SDPHeader(
            destination_chip_x=placement.x, destination_chip_y=placement.y,
            destination_cpu=placement.p, flags=SDPFlag.REPLY_NOT_EXPECTED,
            destination_port=spinn_front_end_constants.SDP_PORTS.
            INPUT_BUFFERING_SDP_PORT.value)
        sdp_message = SDPMessage(sdp_header, message.bytestring)
        self._transceiver.send_sdp_message(sdp_message)

    def stop(self):
        """ Indicates that the simulation has finished, so no further\
            outstanding requests need to be processed
        """
        with self._thread_lock_buffer_in:
            with self._thread_lock_buffer_out:
                self._finished = True
        if self._write_reload_files:
            for buffer_file in self._reload_buffer_file.itervalues():
                buffer_file.close()

    def get_data_for_vertex(self, placement, recording_region_id):
        """ Get a pointer to the data container for all the data retrieved\
            during the simulation from a specific region area of a core

        :param placement: the placement to get the data from
        :type placement: pacman.model.placements.placement.Placement
        :param recording_region_id: desired recording data region
        :type recording_region_id: int
        :return: pointer to a class which inherits from\
                AbstractBufferedDataStorage
        :rtype:\
                py:class:`spinn_front_end_common.interface.buffer_management.buffer_models.abstract_buffered_data_storage.AbstractBufferedDataStorage`
        """

        recording_data_address = \
            placement.vertex.get_recording_region_base_address(
                self._transceiver, placement)

        # Ensure the last sequence number sent has been retrieved
        if not self._received_data.is_end_buffering_sequence_number_stored(
                placement.x, placement.y, placement.p):
            self._received_data.store_end_buffering_sequence_number(
                placement.x, placement.y, placement.p,
                recording_utilities.get_last_sequence_number(
                    placement, self._transceiver, recording_data_address))

        # Read the data if not already received
        if not self._received_data.is_data_from_region_flushed(
                placement.x, placement.y, placement.p,
                recording_region_id):

            # Read the end state of the recording for this region
            if not self._received_data.is_end_buffering_state_recovered(
                    placement.x, placement.y, placement.p,
                    recording_region_id):

                end_state_address = recording_utilities.get_region_pointer(
                    placement, self._transceiver, recording_data_address,
                    recording_region_id)
                end_state = self._generate_end_buffering_state_from_machine(
                    placement, end_state_address)
                self._received_data.store_end_buffering_state(
                    placement.x, placement.y, placement.p, recording_region_id,
                    end_state)
            else:
                end_state = self._received_data.\
                    get_end_buffering_state(
                        placement.x, placement.y, placement.p,
                        recording_region_id)

            start_ptr = end_state.start_address
            write_ptr = end_state.current_write
            end_ptr = end_state.end_address
            read_ptr = end_state.current_read

            # current read needs to be adjusted in case the last portion of the
            # memory has already been read, but the HostDataRead packet has not
            # been processed by the chip before simulation finished
            # This situation is identified by the sequence number of the last
            # packet sent to this core and the core internal state of the
            # output buffering finite state machine
            seq_no_last_ack_packet = \
                self._received_data.last_sequence_no_for_core(
                    placement.x, placement.y, placement.p)

            # get the last sequence number
            last_sequence_number = \
                self._received_data.get_end_buffering_sequence_number(
                    placement.x, placement.y, placement.p)

            if last_sequence_number == seq_no_last_ack_packet:

                # if the last ACK packet has not been processed on the chip,
                # process it now
                last_sent_ack_sdp_packet = \
                    self._received_data.last_sent_packet_to_core(
                        placement.x, placement.y, placement.p)
                last_sent_ack_packet = \
                    create_eieio_command.read_eieio_command_message(
                        last_sent_ack_sdp_packet.data, 0)
                if not isinstance(last_sent_ack_packet, HostDataRead):
                    raise Exception(
                        "Something somewhere went terribly wrong - "
                        "I was looking for a HostDataRead packet, "
                        "while I got {0:s}".format(last_sent_ack_packet))
                for i in xrange(last_sent_ack_packet.n_requests):

                    last_ack_packet_is_of_this_region = \
                        recording_region_id == \
                        last_sent_ack_packet.region_id(i)

                    if (last_ack_packet_is_of_this_region and
                            not end_state.is_state_updated):
                        read_ptr += last_sent_ack_packet.space_read(i)
                        if (read_ptr == write_ptr or
                                (read_ptr == end_ptr and
                                 write_ptr == start_ptr)):
                            end_state.update_last_operation(
                                spinn_front_end_constants.BUFFERING_OPERATIONS.
                                BUFFER_READ.value)
                        if read_ptr == end_ptr:
                            read_ptr = start_ptr
                        elif read_ptr > end_ptr:
                            raise Exception(
                                "Something somewhere went terribly wrong - "
                                "I was reading beyond the region area some "
                                "unknown data".format(
                                    last_sent_ack_packet))
                end_state.update_read_pointer(read_ptr)
                end_state.set_update_completed()

            # now state is updated, read back values for read pointer and
            # last operation performed
            last_operation = end_state.last_buffer_operation
            read_ptr = end_state.current_read

            # now read_ptr is updated, check memory to read
            if read_ptr < write_ptr:
                length = write_ptr - read_ptr
                data = self._transceiver.read_memory(
                    placement.x, placement.y, read_ptr, length)
                self._received_data.flushing_data_from_region(
                    placement.x, placement.y, placement.p, recording_region_id,
                    data)

            elif read_ptr > write_ptr:
                length = end_ptr - read_ptr
                data = self._transceiver.read_memory(
                    placement.x, placement.y, read_ptr, length)
                self._received_data.store_data_in_region_buffer(
                    placement.x, placement.y, placement.p, recording_region_id,
                    data)
                read_ptr = start_ptr
                length = write_ptr - read_ptr
                data = self._transceiver.read_memory(
                    placement.x, placement.y, read_ptr, length)
                self._received_data.flushing_data_from_region(
                    placement.x, placement.y, placement.p, recording_region_id,
                    data)

            elif (read_ptr == write_ptr and
                    last_operation == spinn_front_end_constants.
                    BUFFERING_OPERATIONS.BUFFER_WRITE.value):
                length = end_ptr - read_ptr
                data = self._transceiver.read_memory(
                    placement.x, placement.y, read_ptr, length)
                self._received_data.store_data_in_region_buffer(
                    placement.x, placement.y, placement.p, recording_region_id,
                    data)
                read_ptr = start_ptr
                length = write_ptr - read_ptr
                data = self._transceiver.read_memory(
                    placement.x, placement.y, read_ptr, length)
                self._received_data.flushing_data_from_region(
                    placement.x, placement.y, placement.p, recording_region_id,
                    data)

            elif (read_ptr == write_ptr and
                    last_operation == spinn_front_end_constants.
                    BUFFERING_OPERATIONS.BUFFER_READ.value):
                data = bytearray()
                self._received_data.flushing_data_from_region(
                    placement.x, placement.y, placement.p, recording_region_id,
                    data)

        # data flush has been completed - return appropriate data
        # the two returns can be exchanged - one returns data and the other
        # returns a pointer to the structure holding the data
        return self._received_data.get_region_data_pointer(
            placement.x, placement.y, placement.p, recording_region_id)

    def _retrieve_and_store_data(self, packet):
        """ Following a SpinnakerRequestReadData packet, the data stored\
           during the simulation needs to be read by the host and stored in a\
           data structure, following the specifications of buffering out\
           technique

        :param packet: SpinnakerRequestReadData packet received from the\
                SpiNNaker system
        :type packet:\
                :py:class:`spinnman.messages.eieio.command_messages.spinnaker_request_read_data.SpinnakerRequestReadData`
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
            if last_packet_sent is not None:
                self._transceiver.send_sdp_message(last_packet_sent)
            else:
                raise Exception(
                    "{}, {}, {}: Something somewhere went terribly wrong - "
                    "The packet sequence numbers have gone wrong "
                    "somewhere: the packet sent from the board "
                    "has incorrect sequence number, but the host "
                    "never sent one acknowledge".format(x, y, p))
            return

        # read data from memory, store it and create data for return ACK packet
        n_requests = packet.n_requests
        new_channel = list()
        new_region_id = list()
        new_space_read = list()
        new_n_requests = 0
        for i in xrange(n_requests):
            length = packet.space_to_be_read(i)
            if length > 0:
                new_n_requests += 1
                start_address = packet.start_address(i)
                region_id = packet.region_id(i)
                channel = packet.channel(i)
                data = self._transceiver.read_memory(
                    x, y, start_address, length)
                self._received_data.store_data_in_region_buffer(
                    x, y, p, region_id, data)
                new_channel.append(channel)
                new_region_id.append(region_id)
                new_space_read.append(length)

        # create return acknowledge packet with data stored
        ack_packet = HostDataRead(
            new_n_requests, pkt_seq, new_channel, new_region_id,
            new_space_read)
        ack_packet_data = ack_packet.bytestring

        # create SDP header and message
        return_message_header = SDPHeader(
            destination_port=(
                spinn_front_end_constants.SDP_PORTS
                .OUTPUT_BUFFERING_SDP_PORT.value),
            destination_cpu=p, destination_chip_x=x, destination_chip_y=y,
            flags=SDPFlag.REPLY_NOT_EXPECTED)
        return_message = SDPMessage(return_message_header, ack_packet_data)

        # storage of last packet received
        self._received_data.store_last_received_packet_from_core(
            x, y, p, packet)
        self._received_data.update_sequence_no_for_core(x, y, p, pkt_seq)

        # store last sent message and send to the appropriate core
        self._received_data.store_last_sent_packet_to_core(
            x, y, p, return_message)
        self._transceiver.send_sdp_message(return_message)

    @property
    def sender_vertices(self):
        """ The vertices which are buffered
        """
        return self._sender_vertices

    @property
    def reload_buffer_files(self):
        """ The file paths for each buffered region for each sender vertex
        """
        return self._reload_buffer_file_paths
