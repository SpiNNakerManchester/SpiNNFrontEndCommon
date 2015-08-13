"""
BufferManager
"""

# pacman imports
from pacman.utilities.progress_bar import ProgressBar

# dsg imports
from data_specification import utility_calls as dsg_utilities

# spinnman imports
from spinnman import constants
from spinnman.connections.udp_packet_connections.udp_eieio_connection import \
    UDPEIEIOConnection
from spinnman.messages.eieio.command_messages.eieio_command_message import \
    EIEIOCommandMessage
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.messages.sdp.sdp_message import SDPMessage
from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.messages.eieio.data_messages.eieio_32bit\
    .eieio_32bit_timed_payload_prefix_data_message\
    import EIEIO32BitTimedPayloadPrefixDataMessage
from spinnman.messages.eieio.data_messages.eieio_data_header\
    import EIEIODataHeader
from spinnman.messages.eieio.eieio_type import EIEIOType
from spinnman.exceptions import SpinnmanInvalidPacketException
from spinnman.messages.eieio.data_messages.eieio_data_message \
    import EIEIODataMessage
from spinnman.messages.eieio.command_messages.spinnaker_request_buffers \
    import SpinnakerRequestBuffers
from spinnman.messages.eieio.command_messages.padding_request\
    import PaddingRequest
from spinnman.messages.eieio.command_messages.event_stop_request \
    import EventStopRequest
from spinnman.messages.eieio.command_messages.host_send_sequenced_data\
    import HostSendSequencedData
from spinnman.messages.eieio.command_messages.stop_requests \
    import StopRequests

# front end common imports
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.interface.buffer_management.\
    storage_objects.buffers_sent_deque\
    import BuffersSentDeque

# general imports
import struct
import threading
import logging
import traceback
import math
import os


logger = logging.getLogger(__name__)

# The minimum size of any message - this is the headers plus one entry
_MIN_MESSAGE_SIZE = (EIEIO32BitTimedPayloadPrefixDataMessage
                     .get_min_packet_length())

# The size of the header of a message
_HEADER_SIZE = EIEIODataHeader.get_header_size(EIEIOType.KEY_32_BIT,
                                               is_payload_base=True)

# The number of bytes in each key to be sent
_N_BYTES_PER_KEY = EIEIOType.KEY_32_BIT.key_bytes

# The number of keys allowed (different from the actual number as there is an
# additional header)
_N_KEYS_PER_MESSAGE = (constants.UDP_MESSAGE_MAX_SIZE -
                       (HostSendSequencedData.get_min_packet_length() +
                        _HEADER_SIZE) / _N_BYTES_PER_KEY)


class BufferManager(object):
    """ Manager of send buffers
    """

    def __init__(self, placements, tags, transceiver, report_states,
                 application_folder_path, reload_interface):
        """

        :param placements: The placements of the vertices
        :type placements:\
                    :py:class:`pacman.model.placements.placements.Placements`
        :param report_states: the bools saying what reports are needed
        :type report_states: XXXXXXXXXXX
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
        self._report_states = report_states
        self._application_folder_path = application_folder_path
        self._reload_interface = reload_interface
        self._reload_buffer_file = dict()

        # Set of (ip_address, port) that are being listened to for the tags
        self._seen_tags = set()

        # Set of vertices with buffers to be sent
        self._sender_vertices = set()

        # Dictionary of sender vertex -> buffers sent
        self._sent_messages = dict()

        # Lock to avoid multiple messages being processed at the same time
        self._thread_lock = threading.Lock()

        self._finished = False

    def receive_buffer_command_message(self, packet):
        """ Handle an EIEIO command message for the buffers

        :param packet: The eieio message received
        :type packet:\
                    :py:class:`spinnman.messages.eieio.command_messages.eieio_command_message.EIEIOCommandMessage`
        """
        with self._thread_lock:
            if not self._finished:
                if isinstance(packet, SpinnakerRequestBuffers):
                    vertex = self._placements.get_subvertex_on_processor(
                        packet.x, packet.y, packet.p)

                    if vertex in self._sender_vertices:
                        logger.debug("received packet sequence: {1:d}, "
                                     "space available: {0:d}".format(
                                         packet.space_available,
                                         packet.sequence_no))

                        # noinspection PyBroadException
                        try:
                            self._send_messages(
                                packet.space_available, vertex,
                                packet.region_id, packet.sequence_no)
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

    def add_sender_vertex(self, vertex):
        """ Add a partitioned vertex into the managed list for vertices
            which require buffers to be sent to them during runtime

        :param vertex: the vertex to be managed
        :type vertex:\
                    :py:class:`spinnaker.pyNN.models.abstract_models.buffer_models.abstract_sends_buffers_from_host_partitioned_vertex.AbstractSendsBuffersFromHostPartitionedVertex`
        """
        self._sender_vertices.add(vertex)
        tag = self._tags.get_ip_tags_for_vertex(vertex)[0]
        if (tag.ip_address, tag.port) not in self._seen_tags:
            self._seen_tags.add((tag.ip_address, tag.port))
            self._transceiver.register_udp_listener(
                self.receive_buffer_command_message, UDPEIEIOConnection,
                local_port=tag.port, local_host=tag.ip_address)

        # if reload script is set up, sotre the buffers for future usage
        if self._report_states.transciever_report:
            vertex_files = self._reload_interface.add_buffered_vertex(
                vertex, tag,
                self._placements.get_placement_of_subvertex(vertex))
            for (region, filename) in vertex_files.iteritems():
                file_path = os.path.join(
                    self._application_folder_path, filename)
            self._reload_buffer_file[(vertex, region)] = open(file_path, "w")

    def load_initial_buffers(self):
        """ Load the initial buffers for the senders using mem writes
        """
        total_data = 0
        for vertex in self._sender_vertices:
            for region in vertex.get_regions():
                total_data += vertex.get_region_buffer_size(region)

        progress_bar = ProgressBar(
            total_data, "on loading buffer dependent vertices ({} bytes)"
                        .format(total_data))
        for vertex in self._sender_vertices:
            for region in vertex.get_regions():
                self._send_initial_messages(vertex, region, progress_bar)
        progress_bar.end()

    def _create_message_to_send(self, size, vertex, region):
        """ Creates a single message to send with the given boundaries.

        :param size: The number of bytes available for the whole packet
        :type size: int
        :param vertex: The vertex to get the keys from
        :type vertex:\
                    :py:class:`spynnaker.pyNN.models.abstract_models.buffer_models.abstract_sends_buffers_from_host_partitioned_vertex.AbstractSendsBuffersFromHostPartitionedVertex`
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

            if self._report_states.transciever_report:
                self._reload_buffer_file[(vertex, region)].write(
                    "{}:{}\n".format(next_timestamp, key))

        return message

    @staticmethod
    def get_n_bytes(n_keys):
        """ Get the number of bytes used by a given number of keys

        :param n_keys: The number of keys
        :type n_keys: int
        """

        # Get the total number of messages
        n_messages = int(math.ceil(float(n_keys) / _N_KEYS_PER_MESSAGE))

        # Add up the bytes
        return (_HEADER_SIZE * n_messages) + (n_keys * _N_BYTES_PER_KEY)

    def _send_initial_messages(self, vertex, region, progress_bar):
        """ Send the initial set of messages

        :param vertex: The vertex to get the keys from
        :type vertex:\
                    :py:class:`spynnaker.pyNN.models.abstract_models.buffer_models.abstract_sends_buffers_from_host_partitioned_vertex.AbstractSendsBuffersFromHostPartitionedVertex`
        :param region: The region to get the keys from
        :type region: int
        :return: A list of messages
        :rtype: list of\
                    :py:class:`spinnman.messages.eieio.data_messages.eieio_32bit.eieio_32bit_timed_payload_prefix_data_message.EIEIO32BitTimedPayloadPrefixDataMessage`
        """

        # Get the vertex load details
        region_base_address = self._locate_region_address(region, vertex)
        placement = self._placements.get_placement_of_subvertex(vertex)

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
            while (vertex.is_next_timestamp(region) and
                    bytes_to_go > (EIEIO32BitTimedPayloadPrefixDataMessage
                                   .get_min_packet_length())):
                space_available = min(bytes_to_go, 255 * _N_BYTES_PER_KEY)
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
            logger.debug("Writing stop message of {} bytes to {} on"
                         " {}, {}, {}".format(
                             len(data), hex(region_base_address),
                             placement.x, placement.y, placement.p))
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
            logger.debug(
                "Bytes to go {}, space available {}, timestamp {}"
                .format(bytes_to_go, space_available,
                        vertex.get_next_timestamp(region)))
            next_message = self._create_message_to_send(
                space_available, vertex, region)
            if next_message is None:
                break
            sent_messages.add_message_to_send(next_message)
            bytes_to_go -= next_message.size
            logger.debug("Adding additional buffer of {} bytes".format(
                next_message.size))

        # If the vertex is empty, send the stop messages if there is space
        if (not sent_messages.is_full and
                not vertex.is_next_timestamp(region) and
                bytes_to_go >= EventStopRequest.get_min_packet_length()):
            sent_messages.send_stop_message()
            if self._report_states.transciever_report:
                self._reload_buffer_file[(vertex, region)].close()

        # If there are no more messages, turn off requests for more messages
        if not vertex.is_next_timestamp(region) and sent_messages.is_empty():
            logger.debug("Sending stop")
            self._send_request(vertex, StopRequests())

        # Send the messages
        for message in sent_messages.messages:
            logger.debug("Sending message with sequence {}".format(
                message.sequence_no))
            self._send_request(vertex, message)

    def _locate_region_address(self, region, vertex):
        """ Get the address of a region for a vertex

        :param region: the region to locate the base address of
        :type region: int
        :param vertex: the vertex to load a buffer for
        :type vertex:\
                    :py:class:`spynnaker.pyNN.models.abstract_models.buffer_models.abstract_sends_buffers_from_host_partitioned_vertex.AbstractSendsBuffersFromHostPartitionedVertex`
        :return: None
        """
        placement = self._placements.get_placement_of_subvertex(vertex)
        app_data_base_address = \
            self._transceiver.get_cpu_information_from_core(
                placement.x, placement.y, placement.p).user[0]

        # Get the position of the region in the pointer table
        region_offset_in_pointer_table = \
            dsg_utilities.get_region_base_address_offset(
                app_data_base_address, region)
        region_offset = self._transceiver.read_memory(
            placement.x, placement.y, region_offset_in_pointer_table, 4)
        return (struct.unpack_from("<I", region_offset)[0] +
                app_data_base_address)

    def _send_request(self, vertex, message):
        """ Sends a request

        :param vertex: The vertex to send to
        :param message: The message to send
        """

        placement = self._placements.get_placement_of_subvertex(vertex)
        sdp_header = SDPHeader(
            destination_chip_x=placement.x, destination_chip_y=placement.y,
            destination_cpu=placement.p, flags=SDPFlag.REPLY_NOT_EXPECTED,
            destination_port=1)
        sdp_message = SDPMessage(sdp_header, message.bytestring)
        self._transceiver.send_sdp_message(sdp_message)

    def stop(self):
        """ Indicates that the simulation has finished, so no further\
            outstanding requests need to be processed
        """
        with self._thread_lock:
            self._finished = True
