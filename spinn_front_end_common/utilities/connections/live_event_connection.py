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
import struct
import sys
from threading import Thread
try:
    from collections.abc import OrderedDict
except ImportError:
    from collections import OrderedDict
from six import iterkeys, iteritems, reraise
from spinn_utilities.log import FormatAdapter
from spinnman.messages.eieio.data_messages import (
    EIEIODataMessage, KeyPayloadDataElement)
from spinnman.messages.eieio import EIEIOType
from spinnman.connections import ConnectionListener
from spinnman.connections.udp_packet_connections import EIEIOConnection
from spinn_front_end_common.utilities.constants import NOTIFY_PORT
from spinn_front_end_common.utilities.database import DatabaseConnection
from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.connections.udp_packet_connections.utils import (
    update_sdp_header_for_udp_send)
from spinnman.messages.scp.impl.iptag_set import IPTagSet
from spinnman.exceptions import SpinnmanTimeoutException
from spinnman.constants import SCP_SCAMP_PORT
from spinnman.utilities.utility_functions import send_port_trigger_message
from spinnman.messages.sdp.sdp_message import SDPMessage
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.connections.udp_packet_connections import UDPConnection

logger = FormatAdapter(logging.getLogger(__name__))

# The maximum number of 32-bit keys that will fit in a packet
_MAX_FULL_KEYS_PER_PACKET = 63

# The maximum number of 16-bit keys that will fit in a packet
_MAX_HALF_KEYS_PER_PACKET = 127

_TWO_SKIP = struct.Struct("<2x")


class LiveEventConnection(DatabaseConnection):
    """ A connection for receiving and sending live events from and to\
        SpiNNaker
    """
    __slots__ = [
        "_atom_id_to_key",
        "_init_callbacks",
        "_key_to_atom_id_and_label",
        "_live_event_callbacks",
        "_live_packet_gather_label",
        "_machine_vertices",
        "_pause_stop_callbacks",
        "_receive_labels",
        "_receiver_connection",
        "_receiver_listener",
        "_send_address_details",
        "_send_labels",
        "_sender_connection",
        "_start_resume_callbacks",
        "_error_keys"]

    def __init__(self, live_packet_gather_label, receive_labels=None,
                 send_labels=None, local_host=None, local_port=NOTIFY_PORT,
                 machine_vertices=False):
        """
        :param live_packet_gather_label: The label of the LivePacketGather\
            vertex to which received events are being sent
        :param receive_labels: \
            Labels of vertices from which live events will be received.
        :type receive_labels: iterable(str)
        :param send_labels: \
            Labels of vertices to which live events will be sent
        :type send_labels: iterable(str)
        :param local_host: Optional specification of the local hostname or\
            IP address of the interface to listen on
        :type local_host: str
        :param local_port: Optional specification of the local port to listen\
            on. Must match the port that the toolchain will send the\
            notification on (19999 by default)
        :type local_port: int
        """
        # pylint: disable=too-many-arguments
        super(LiveEventConnection, self).__init__(
            self._start_resume_callback, self._stop_pause_callback,
            local_host=local_host, local_port=local_port)

        self.add_database_callback(self._read_database_callback)

        self._live_packet_gather_label = live_packet_gather_label
        self._receive_labels = (
            list(receive_labels) if receive_labels is not None else None)
        self._send_labels = (
            list(send_labels) if send_labels is not None else None)
        self._machine_vertices = machine_vertices
        self._sender_connection = None
        self._send_address_details = dict()
        self._atom_id_to_key = dict()
        self._key_to_atom_id_and_label = dict()
        self._live_event_callbacks = list()
        self._start_resume_callbacks = dict()
        self._pause_stop_callbacks = dict()
        self._init_callbacks = dict()
        if receive_labels is not None:
            for label in receive_labels:
                self._live_event_callbacks.append(list())
                self._start_resume_callbacks[label] = list()
                self._pause_stop_callbacks[label] = list()
                self._init_callbacks[label] = list()
        if send_labels is not None:
            for label in send_labels:
                self._start_resume_callbacks[label] = list()
                self._pause_stop_callbacks[label] = list()
                self._init_callbacks[label] = list()
        self._receiver_listener = None
        self._receiver_connection = None
        self._error_keys = set()

    def add_send_label(self, label):
        if self._send_labels is None:
            self._send_labels = list()
        if label not in self._send_labels:
            self._send_labels.append(label)
        if label not in self._start_resume_callbacks:
            self._start_resume_callbacks[label] = list()
            self._pause_stop_callbacks[label] = list()
            self._init_callbacks[label] = list()

    def add_receive_label(self, label):
        if self._receive_labels is None:
            self._receive_labels = list()
        if label not in self._receive_labels:
            self._receive_labels.append(label)
            self._live_event_callbacks.append(list())
        if label not in self._start_resume_callbacks:
            self._start_resume_callbacks[label] = list()
            self._pause_stop_callbacks[label] = list()
            self._init_callbacks[label] = list()

    def add_init_callback(self, label, init_callback):
        """ Add a callback to be called to initialise a vertex

        :param label: The label of the vertex to be notified about. Must be\
            one of the vertices listed in the constructor
        :type label: str
        :param init_callback: A function to be called to initialise the\
            vertex. This should take as parameters the label of the vertex,\
            the number of neurons in the population, the run time of the\
            simulation in milliseconds, and the simulation timestep in\
            milliseconds
        :type init_callback: function(str, int, float, float) -> None
        """
        self._init_callbacks[label].append(init_callback)

    def add_receive_callback(self, label, live_event_callback):
        """ Add a callback for the reception of live events from a vertex

        :param label: The label of the vertex to be notified about. Must be\
            one of the vertices listed in the constructor
        :type label: str
        :param live_event_callback: A function to be called when events are\
            received. This should take as parameters the label of the vertex,\
            the simulation timestep when the event occurred, and an\
            array-like of atom IDs.
        :type live_event_callback: function(str, int, list(int)) -> None
        """
        label_id = self._receive_labels.index(label)
        logger.info("Receive callback {} registered to label {}".format(
            live_event_callback, label))
        self._live_event_callbacks[label_id].append(live_event_callback)

    def add_start_callback(self, label, start_callback):
        """ Add a callback for the start of the simulation

        :param start_callback: A function to be called when the start\
            message has been received. This function should take the label of\
            the referenced vertex, and an instance of this class, which can\
            be used to send events
        :type start_callback: function(str, \
            :py:class:`SpynnakerLiveEventConnection`) -> None
        :param label: the label of the function to be sent
        :type label: str
        """
        logger.warning(
            "the method 'add_start_callback(label, start_callback)' is in "
            "deprecation, and will be replaced with the method "
            "'add_start_resume_callback(label, start_resume_callback)' in a "
            "future release.")
        self.add_start_resume_callback(label, start_callback)

    def add_start_resume_callback(self, label, start_resume_callback):
        self._start_resume_callbacks[label].append(start_resume_callback)

    def add_pause_stop_callback(self, label, pause_stop_callback):
        """ Add a callback for the pause and stop state of the simulation

        :param label: the label of the function to be sent
        :type label: str
        :param pause_stop_callback: A function to be called when the pause\
            or stop message has been received. This function should take the\
            label of the referenced  vertex, and an instance of this class,\
            which can be used to send events.
        :type pause_stop_callback: function(str, \
            :py:class:`SpynnakerLiveEventConnection`) -> None
        :rtype: None
        """
        self._pause_stop_callbacks[label].append(pause_stop_callback)

    def _read_database_callback(self, db_reader):
        self._handle_possible_rerun_state()

        vertex_sizes = OrderedDict()
        run_time_ms = db_reader.get_configuration_parameter_value(
            "runtime")
        machine_timestep_ms = db_reader.get_configuration_parameter_value(
            "machine_time_step") / 1000.0

        if self._send_labels is not None:
            self._init_sender(db_reader, vertex_sizes)

        if self._receive_labels is not None:
            self._init_receivers(db_reader, vertex_sizes)

        for label, vertex_size in iteritems(vertex_sizes):
            for init_callback in self._init_callbacks[label]:
                init_callback(
                    label, vertex_size, run_time_ms, machine_timestep_ms)

    def _init_sender(self, db, vertex_sizes):
        if self._sender_connection is None:
            self._sender_connection = UDPConnection()
        for label in self._send_labels:
            self._send_address_details[label] = self.__get_live_input_details(
                db, label)
            if self._machine_vertices:
                key, _ = db.get_machine_live_input_key(label)
                self._atom_id_to_key[label] = {0: key}
                vertex_sizes[label] = 1
            else:
                self._atom_id_to_key[label] = db.get_atom_id_to_key_mapping(
                    label)
                vertex_sizes[label] = len(self._atom_id_to_key[label])

    def _init_receivers(self, db, vertex_sizes):
        # Set up a single connection for receive
        if self._receiver_connection is None:
            self._receiver_connection = EIEIOConnection()
        receivers = set()
        for label_id, label in enumerate(self._receive_labels):
            _, port, board_address, tag = self.__get_live_output_details(
                db, label)

            # Update the tag if not already done
            if (board_address, port, tag) not in receivers:
                self.__update_tag(
                    self._receiver_connection, board_address, tag)
                receivers.add((board_address, port, tag))
                send_port_trigger_message(
                    self._receiver_connection, board_address)

            logger.info(
                "Listening for traffic from {} on {}:{}",
                label, self._receiver_connection.local_ip_address,
                self._receiver_connection.local_port)

            if self._machine_vertices:
                key, _ = db.get_machine_live_output_key(
                    label, self._live_packet_gather_label)
                self._key_to_atom_id_and_label[key] = (0, label_id)
                vertex_sizes[label] = 1
            else:
                key_to_atom_id = db.get_key_to_atom_id_mapping(label)
                for key, atom_id in iteritems(key_to_atom_id):
                    self._key_to_atom_id_and_label[key] = (atom_id, label_id)
                vertex_sizes[label] = len(key_to_atom_id)

        # Last of all, set up the listener for packets
        # NOTE: Has to be done last as otherwise will receive SCP messages
        # sent above!
        if self._receiver_listener is None:
            self._receiver_listener = ConnectionListener(
                self._receiver_connection)
            self._receiver_listener.add_callback(self._receive_packet_callback)
            self._receiver_listener.start()

    def __get_live_input_details(self, db_reader, send_label):
        if self._machine_vertices:
            x, y, p = db_reader.get_placement(send_label)
        else:
            x, y, p = db_reader.get_placements(send_label)[0]

        ip_address = db_reader.get_ip_address(x, y)
        return x, y, p, ip_address

    def __get_live_output_details(self, db_reader, receive_label):
        if self._machine_vertices:
            host, port, strip_sdp, board_address, tag = \
                db_reader.get_machine_live_output_details(
                    receive_label, self._live_packet_gather_label)
        else:
            host, port, strip_sdp, board_address, tag = \
                db_reader.get_live_output_details(
                    receive_label, self._live_packet_gather_label)
        if not strip_sdp:
            raise Exception("Currently, only IP tags which strip the SDP "
                            "headers are supported")
        return host, port, board_address, tag

    def __update_tag(self, connection, board_address, tag):
        # Update an IP Tag with the sender's address and port
        # This avoids issues with NAT firewalls
        logger.debug("Updating tag for {}".format(board_address))
        request = IPTagSet(
            0, 0, [0, 0, 0, 0], 0, tag, strip=True, use_sender=True)
        request.sdp_header.flags = SDPFlag.REPLY_EXPECTED_NO_P2P
        update_sdp_header_for_udp_send(request.sdp_header, 0, 0)
        data = _TWO_SKIP.pack() + request.bytestring
        sent = False
        tries_to_go = 3
        while not sent:
            try:
                connection.send_to(data, (board_address, SCP_SCAMP_PORT))
                response_data = connection.receive(1.0)
                request.get_scp_response().read_bytestring(response_data, 2)
                sent = True
            except SpinnmanTimeoutException:
                if not tries_to_go:
                    logger.info("No more tries - Error!")
                    reraise(*sys.exc_info())

                logger.info("Timeout, retrying")
                tries_to_go -= 1
        logger.debug("Done updating tag for {}".format(board_address))

    def _handle_possible_rerun_state(self):
        # reset from possible previous calls
        if self._sender_connection is not None:
            self._sender_connection.close()
            self._sender_connection = None
        if self._receiver_listener is not None:
            self._receiver_listener.close()
            self._receiver_listener = None
        if self._receiver_connection is not None:
            self._receiver_connection.close()
            self._receiver_connection = None

    def __launch_thread(self, kind, label, callback):
        thread = Thread(
            target=callback, args=(label, self),
            name="{} callback thread for live_event_connection {}:{}".format(
                kind, self._local_port, self._local_ip_address))
        thread.start()

    def _start_resume_callback(self):
        for label, callbacks in iteritems(self._start_resume_callbacks):
            for callback in callbacks:
                self.__launch_thread("start_resume", label, callback)

    def _stop_pause_callback(self):
        for label, callbacks in iteritems(self._pause_stop_callbacks):
            for callback in callbacks:
                self.__launch_thread("pause_stop", label, callback)

    def _receive_packet_callback(self, packet):
        logger.debug("Received packet")
        try:
            if packet.eieio_header.is_time:
                self.__handle_time_packet(packet)
            else:
                self.__handle_no_time_packet(packet)
        except Exception:
            logger.warning("problem handling received packet", exc_info=True)

    def __handle_time_packet(self, packet):
        key_times_labels = OrderedDict()
        while packet.is_next_element:
            element = packet.next_element
            time = element.payload
            key = element.key
            if key in self._key_to_atom_id_and_label:
                atom_id, label_id = self._key_to_atom_id_and_label[key]
                if time not in key_times_labels:
                    key_times_labels[time] = dict()
                if label_id not in key_times_labels[time]:
                    key_times_labels[time][label_id] = list()
                key_times_labels[time][label_id].append(atom_id)
            else:
                self.__handle_unknown_key(key)

        for time in iterkeys(key_times_labels):
            for label_id in iterkeys(key_times_labels[time]):
                label = self._receive_labels[label_id]
                for callback in self._live_event_callbacks[label_id]:
                    callback(label, time, key_times_labels[time][label_id])

    def __handle_no_time_packet(self, packet):
        while packet.is_next_element:
            element = packet.next_element
            key = element.key
            if key in self._key_to_atom_id_and_label:
                atom_id, label_id = self._key_to_atom_id_and_label[key]
                for callback in self._live_event_callbacks[label_id]:
                    if isinstance(element, KeyPayloadDataElement):
                        callback(self._receive_labels[label_id], atom_id,
                                 element.payload)
                    else:
                        callback(self._receive_labels[label_id], atom_id)
            else:
                self.__handle_unknown_key(key)

    def __handle_unknown_key(self, key):
        if key not in self._error_keys:
            self._error_keys.add(key)
            logger.warning("Received unexpected key {}".format(key))

    def send_event(self, label, atom_id, send_full_keys=False):
        """ Send an event from a single atom

        :param label: \
            The label of the vertex from which the event will originate
        :type label: str
        :param atom_id: The ID of the atom sending the event
        :type atom_id: int
        :param send_full_keys: Determines whether to send full 32-bit keys,\
            getting the key for each atom from the database, or whether to\
            send 16-bit atom IDs directly
        :type send_full_keys: bool
        """
        self.send_events(label, [atom_id], send_full_keys)

    def send_events(self, label, atom_ids, send_full_keys=False):
        """ Send a number of events

        :param label: \
            The label of the vertex from which the events will originate
        :type label: str
        :param atom_ids: array-like of atom IDs sending events
        :type atom_ids: list(int)
        :param send_full_keys: Determines whether to send full 32-bit keys,\
            getting the key for each atom from the database, or whether to\
            send 16-bit atom IDs directly
        :type send_full_keys: bool
        """
        max_keys = _MAX_HALF_KEYS_PER_PACKET
        msg_type = EIEIOType.KEY_16_BIT
        if send_full_keys:
            max_keys = _MAX_FULL_KEYS_PER_PACKET
            msg_type = EIEIOType.KEY_32_BIT

        pos = 0
        x, y, p, ip_address = self._send_address_details[label]
        while pos < len(atom_ids):
            message = EIEIODataMessage.create(msg_type)
            events_in_packet = 0
            while pos < len(atom_ids) and events_in_packet < max_keys:
                key = atom_ids[pos]
                if send_full_keys:
                    key = self._atom_id_to_key[label][key]
                message.add_key(key)
                pos += 1
                events_in_packet += 1

            self._sender_connection.send_to(
                self._get_sdp_data(message, x, y, p),
                (ip_address, SCP_SCAMP_PORT))

    def close(self):
        self._handle_possible_rerun_state()
        DatabaseConnection.close(self)

    @staticmethod
    def _get_sdp_data(message, x, y, p):
        # Create an SDP message - no reply so source is unimportant
        # SDP port can be anything except 0 as the target doesn't care
        sdp_message = SDPMessage(
            SDPHeader(
                flags=SDPFlag.REPLY_NOT_EXPECTED, tag=0,
                destination_port=1, destination_cpu=p,
                destination_chip_x=x, destination_chip_y=y,
                source_port=0, source_cpu=0,
                source_chip_x=0, source_chip_y=0),
            data=message.bytestring)
        return _TWO_SKIP.pack() + sdp_message.bytestring
