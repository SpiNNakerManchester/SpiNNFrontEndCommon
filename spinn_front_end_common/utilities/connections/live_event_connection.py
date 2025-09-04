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
from collections import defaultdict
import logging
import struct
from threading import Thread, Condition
from time import sleep
from typing import (
    Callable, Dict, Iterable, List, Optional, Set, Tuple, Union,
    cast)

from typing_extensions import TypeGuard

from spinn_utilities.log import FormatAdapter
from spinn_utilities.logger_utils import warn_once

from spinnman.messages.eieio.data_messages import (
    EIEIODataMessage, KeyPayloadDataElement, KeyDataElement)
from spinnman.messages.eieio import EIEIOType, AbstractEIEIOMessage
from spinnman.connections import ConnectionListener
from spinnman.connections.udp_packet_connections import (
    EIEIOConnection, UDPConnection)
from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.constants import SCP_SCAMP_PORT
from spinnman.messages.sdp.sdp_message import SDPMessage
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.utilities.utility_functions import reprogram_tag_to_listener
from spinnman.messages.eieio import (
    read_eieio_command_message, read_eieio_data_message)
from spinnman.spalloc import SpallocEIEIOConnection, SpallocEIEIOListener

from spinn_front_end_common.utilities.constants import NOTIFY_PORT
from spinn_front_end_common.utilities.database import (
    DatabaseConnection, DatabaseReader)
from spinn_front_end_common.utilities.exceptions import ConfigurationException

_InitCallback = Callable[[str, int, float, float], None]
_RcvCallback = Callable[[str, int, Optional[int]], None]
_RcvTimeCallback = Callable[[str, int, List[int]], None]
_Callback = Callable[[str, 'LiveEventConnection'], None]
logger = FormatAdapter(logging.getLogger(__name__))

# The maximum number of 32-bit keys that will fit in a packet
_MAX_FULL_KEYS_PER_PACKET = 63

# The maximum number of 16-bit keys that will fit in a packet
_MAX_HALF_KEYS_PER_PACKET = 127

# The maximum number of 32-bit keys with payloads that will fit in a packet
_MAX_FULL_KEYS_PAYLOADS_PER_PACKET = 31

# The maximum number of packets to send before pausing
_MAX_SEND_BEFORE_PAUSE = 6

# Decoding of a single short value
_ONE_SHORT = struct.Struct("<H")

# The size of a RAW SCP OK response (includes 2 bytes of padding)
_SCP_OK_SIZE = 18

# The byte of the RAW SCP packet that contains the flags
_SCP_FLAGS_BYTE = 2

# The byte of the RAW SCP packet that contains the destination cpu
_SCP_DEST_CPU_BYTE = 4

# The expected flags from a RAW SCP packet in response
_SCP_RESPONSE_FLAGS = 7

# The expected destination cpu from a RAW SCP packet in response
_SCP_RESPONSE_DEST = 0xFF


def _is_spalloc_eieio(val: UDPConnection) -> TypeGuard[Union[
        SpallocEIEIOConnection, SpallocEIEIOListener]]:
    """
    Do we have a proxied EIEIO connection?
    """
    return hasattr(val, "update_tag")


class LiveEventConnection(DatabaseConnection):
    """
    A connection for receiving and sending live events from and to SpiNNaker.

    .. note::
        This class is intended to be potentially usable from another
        process than the one that the simulator is present in.
    """
    __slots__ = (
        "_atom_id_to_key",
        "__error_keys",
        "__init_callbacks",
        "__key_to_atom_id_and_label",
        "__no_time_event_callbacks",
        "__time_event_callbacks",
        "__live_packet_gather_label",
        "__pause_stop_callbacks",
        "__receive_labels",
        "__receiver_connection",
        "__receiver_listener",
        "__send_address_details",
        "__send_labels",
        "__sender_connection",
        "__start_resume_callbacks",
        "__simulator",
        "__spalloc_job",
        "__receiver_details",
        "__is_running",
        "__expect_scp_response",
        "__expect_scp_response_lock",
        "__scp_response_received",
        "__tag_update_thread",
        "__send_tag_update_thread_lock")

    def __init__(self, live_packet_gather_label: Optional[str],
                 receive_labels: Optional[Iterable[str]] = None,
                 send_labels: Optional[Iterable[str]] = None,
                 local_host: Optional[str] = None,
                 local_port: Optional[int] = NOTIFY_PORT):
        """
        :param live_packet_gather_label:
            The label of the vertex to which received events are being sent.
            If `None`, no receive labels may be specified.
        :param receive_labels:
            Labels of vertices from which live events will be received.
        :param send_labels:
            Labels of vertices to which live events will be sent
        :param local_host:
            Optional specification of the local hostname or IP address of the
            interface to listen on
        :param local_port:
            Optional specification of the local port to listen on. Must match
            the port that the toolchain will send the notification on (19999
            by default)
        """
        super().__init__(
            self.__do_start_resume, self.__do_stop_pause,
            local_host=local_host, local_port=local_port)

        self.add_database_callback(self.__read_database_callback)

        self.__live_packet_gather_label = live_packet_gather_label
        if self.__live_packet_gather_label is None and (
                receive_labels is not None):
            raise ConfigurationException("may only specify ")
        self.__receive_labels = (
            list(receive_labels) if receive_labels is not None else None)
        self.__send_labels = (
            list(send_labels) if send_labels is not None else None)
        self.__sender_connection: Optional[EIEIOConnection] = None
        self.__send_address_details: Dict[str, Tuple[
            int, int, int, str]] = dict()
        # Also used by SpynnakerPoissonControlConnection
        self._atom_id_to_key: Dict[str, Dict[int, int]] = dict()
        self.__key_to_atom_id_and_label: Dict[int, Tuple[int, int]] = dict()
        self.__no_time_event_callbacks: List[
            List[Tuple[_RcvCallback, bool]]] = list()
        self.__time_event_callbacks: List[
            List[Tuple[Union[_RcvTimeCallback], bool]]] = list()
        self.__start_resume_callbacks: Dict[str, List[_Callback]] = dict()
        self.__pause_stop_callbacks: Dict[str, List[_Callback]] = dict()
        self.__init_callbacks: Dict[str, List[_InitCallback]] = dict()
        self.__receiver_details: List[Tuple[int, int, int, str]] = list()
        if receive_labels is not None:
            for label in receive_labels:
                self.__no_time_event_callbacks.append(list())
                self.__time_event_callbacks.append(list())
                self.__start_resume_callbacks[label] = list()
                self.__pause_stop_callbacks[label] = list()
                self.__init_callbacks[label] = list()
        if send_labels is not None:
            for label in send_labels:
                self.__start_resume_callbacks[label] = list()
                self.__pause_stop_callbacks[label] = list()
                self.__init_callbacks[label] = list()
        self.__receiver_listener: Optional[ConnectionListener] = None
        self.__receiver_connection: Optional[UDPConnection] = None
        self.__error_keys: Set[int] = set()
        self.__is_running = False
        self.__tag_update_thread: Optional[Thread] = None
        self.__send_tag_update_thread_lock = Condition()
        self.__expect_scp_response = False
        self.__expect_scp_response_lock = Condition()
        self.__scp_response_received: Optional[bytes] = None

    def add_send_label(self, label: str) -> None:
        """
        Adds a send label.

        :param label:
        """
        if self.__send_labels is None:
            self.__send_labels = list()
        if label not in self.__send_labels:
            self.__send_labels.append(label)
        if label not in self.__start_resume_callbacks:
            self.__start_resume_callbacks[label] = list()
            self.__pause_stop_callbacks[label] = list()
            self.__init_callbacks[label] = list()

    def add_receive_label(self, label: str) -> None:
        """
        Adds a receive label is possible.

        :param label:
        """
        if self.__live_packet_gather_label is None:
            raise ConfigurationException(
                "no live packet gather label given; "
                "receive labels not supported")
        if self.__receive_labels is None:
            self.__receive_labels = list()
        if label not in self.__receive_labels:
            self.__receive_labels.append(label)
            self.__no_time_event_callbacks.append(list())
            self.__time_event_callbacks.append(list())
        if label not in self.__start_resume_callbacks:
            self.__start_resume_callbacks[label] = list()
            self.__pause_stop_callbacks[label] = list()
            self.__init_callbacks[label] = list()

    def add_init_callback(
            self, label: str, init_callback: _InitCallback) -> None:
        """
        Add a callback to be called to initialise a vertex.

        :param label:
            The label of the vertex to be notified about. Must be one of the
            vertices listed in the constructor
        :param init_callback: A function to be called to initialise the
            vertex. This should take as parameters the label of the vertex,
            the number of neurons in the population, the run time of the
            simulation in milliseconds, and the simulation timestep in
            milliseconds
        """
        self.__init_callbacks[label].append(init_callback)

    def add_receive_callback(
            self, label: str, live_event_callback: _RcvTimeCallback,
            translate_key: bool = True) -> None:
        """
        Add a callback for the reception of time events from a vertex.

        These are typically used to receive keys or atoms ids that spiked.

        .. note::
            Previously this method was also used to add no time callback
            I.e. the once that take as parameters the label of the vertex,
            an int atom ID or key, and an int payload which may be None.
            For those use add_receive_no_time_callback now

        :param label: The label of the vertex to be notified about.
            Must be one of the vertices listed in the constructor
        :param live_event_callback: A function to be called when events are
            received. This should take as parameters the label of the vertex,
            the simulation timestep when the event occurred, and an
            array-like of atom IDs or keys.
        :param translate_key:
            True if the key is to be converted to an atom ID, False if the
            key should stay a key
        """
        if self.__receive_labels is None:
            raise ConfigurationException("no receive labels defined")
        label_id = self.__receive_labels.index(label)
        logger.info("Receive callback {} registered to label {}",
                    live_event_callback, label)
        self.__time_event_callbacks[label_id].append(
            (live_event_callback, translate_key))

    def add_receive_no_time_callback(
            self, label: str, live_event_callback: _RcvCallback,
            translate_key: bool = True) -> None:
        """
        Add a callback for the reception of live events from a vertex.

        :param label: The label of the vertex to be notified about.
            Must be one of the vertices listed in the constructor
        :param live_event_callback: A function to be called when events are
            received. This should take as parameters the label of the vertex,
            an int atom ID or key, and an int payload which may be None
        :param translate_key: If True the key will be converted to an atom id
            before calling live_event_callback
        """
        if self.__receive_labels is None:
            raise ConfigurationException("no receive labels defined")
        label_id = self.__receive_labels.index(label)
        logger.info("Receive callback {} registered to label {}",
                    live_event_callback, label)
        self.__no_time_event_callbacks[label_id].append(
            (live_event_callback, translate_key))

    def add_start_callback(
            self, label: str, start_callback: _Callback) -> None:
        """
        Add a callback for the start of the simulation.

        :param start_callback: A function to be called when the start
            message has been received. This function should take the label of
            the referenced vertex, and an instance of this class, which can
            be used to send events
        :param label: the label of the function to be sent
        """
        logger.warning(
            "the method 'add_start_callback(label, start_callback)' is in "
            "deprecation, and will be replaced with the method "
            "'add_start_resume_callback(label, start_resume_callback)' in a "
            "future release.")
        self.add_start_resume_callback(label, start_callback)

    def add_start_resume_callback(
            self, label: str, start_resume_callback: _Callback) -> None:
        """
        Add a callback for the start and resume state of the simulation.

        :param label: the label of the function to be sent
        :param start_resume_callback: A function to be called when the start
            or resume message has been received. This function should take
            the label of the referenced vertex, and an instance of this
            class, which can be used to send events.
        """
        self.__start_resume_callbacks[label].append(start_resume_callback)

    def add_pause_stop_callback(
            self, label: str, pause_stop_callback: _Callback) -> None:
        """
        Add a callback for the pause and stop state of the simulation.

        :param label: the label of the function to be sent
        :param pause_stop_callback: A function to be called when the pause
            or stop message has been received. This function should take the
            label of the referenced  vertex, and an instance of this class,
            which can be used to send events.
        """
        self.__pause_stop_callbacks[label].append(pause_stop_callback)

    def __read_database_callback(self, db_reader: DatabaseReader) -> None:
        self.__handle_possible_rerun_state()

        vertex_sizes: Dict[str, int] = dict()
        run_time_ms = db_reader.get_configuration_parameter_value(
            "runtime")
        machine_timestep = db_reader.get_configuration_parameter_value(
            "machine_time_step")
        assert run_time_ms is not None
        assert machine_timestep is not None

        if self.__send_labels is not None:
            self.__init_sender(db_reader, vertex_sizes)

        if self.__receive_labels is not None:
            self.__init_receivers(db_reader, vertex_sizes)

        for label, vertex_size in vertex_sizes.items():
            for init_callback in self.__init_callbacks[label]:
                init_callback(
                    label, vertex_size, run_time_ms, machine_timestep / 1000.0)

    def __init_sender(self, database: DatabaseReader,
                      vertex_sizes: Dict[str, int]) -> None:
        if self.__sender_connection is None:
            job = database.get_job()
            if job:
                self.__sender_connection = job.open_eieio_listener_connection()
            else:
                self.__sender_connection = EIEIOConnection()
        if self.__send_labels is None:
            raise ConfigurationException("no send labels defined")
        for label in self.__send_labels:
            self.__send_address_details[label] = self.__get_live_input_details(
                database, label)
            self._atom_id_to_key[label] = \
                database.get_atom_id_to_key_mapping(label)
            vertex_sizes[label] = len(self._atom_id_to_key[label])

    def __init_receivers(self, database: DatabaseReader,
                         vertex_sizes: Dict[str, int]) -> None:
        # Set up a single connection for receive
        if self.__receiver_connection is None:
            job = database.get_job()
            if job:
                self.__receiver_connection = job.open_udp_listener_connection()
            else:
                self.__receiver_connection = UDPConnection()
        receivers = set()
        if self.__receive_labels is None:
            raise ConfigurationException("no receive labels defined")
        for label_id, label in enumerate(self.__receive_labels):
            _, port, board_address, tag, x, y = self.__get_live_output_details(
                database, label)

            # Update the tag if not already done
            if (board_address, port, tag) not in receivers:
                receivers.add((board_address, port, tag))
                self.__receiver_details.append((x, y, tag, board_address))

            logger.info(
                "Listening for traffic from {} on board {} on {}:{}",
                label, board_address,
                self.__receiver_connection.local_ip_address,
                self.__receiver_connection.local_port)

            key_to_atom_id = database.get_key_to_atom_id_mapping(label)
            for key, atom_id in key_to_atom_id.items():
                self.__key_to_atom_id_and_label[key] = (atom_id, label_id)
            vertex_sizes[label] = len(key_to_atom_id)

        # Last of all, set up the listener for packets
        # NOTE: Has to be done last as otherwise will receive SCP messages
        # sent above!
        if self.__receiver_listener is None:
            self.__receiver_listener = ConnectionListener(
                self.__receiver_connection)
            self.__receiver_listener.add_callback(self.__do_receive_packet)
            self.__receiver_listener.start()
            self.__send_tag_messages_now()

    def __get_live_input_details(
            self, db_reader: DatabaseReader, send_label: str) -> Tuple[
                int, int, int, str]:
        x, y, p = db_reader.get_placements(send_label)[0]

        ip_address = db_reader.get_ip_address(x, y)
        if ip_address is None:
            raise ConfigurationException(
                f"Ethernet-enabled chip without IP address at {x},{y}")
        return x, y, p, ip_address

    def __get_live_output_details(
            self, db_reader: DatabaseReader, receive_label: str) -> Tuple[
                str, int, str, int, int, int]:
        assert self.__live_packet_gather_label is not None
        host, port, strip_sdp, board_address, tag, chip_x, chip_y = \
            db_reader.get_live_output_details(
                receive_label, self.__live_packet_gather_label)
        if host is None:
            raise ConfigurationException(
                f"no live output tag found for {receive_label} in app graph")
        if not strip_sdp:
            raise ConfigurationException(
                "Currently, only IP tags which strip the SDP headers "
                "are supported")
        return host, port, board_address, tag, chip_x, chip_y

    def __handle_possible_rerun_state(self) -> None:
        # reset from possible previous calls
        if self.__sender_connection is not None:
            self.__sender_connection.close()
            self.__sender_connection = None
        if self.__receiver_listener is not None:
            self.__receiver_listener.close()
            self.__receiver_listener = None
        if self.__receiver_connection is not None:
            self.__receiver_connection.close()
            self.__receiver_connection = None

    def __launch_thread(
            self, kind: str, label: str, callback: _Callback) -> None:
        thread = Thread(
            target=callback, args=(label, self),
            name=(f"{kind} callback thread for live_event_connection "
                  f"{self._local_port}:{self._local_ip_address}"))
        thread.start()

    def __do_start_resume(self) -> None:
        while self.__tag_update_thread is not None:
            sleep(0.5)
        for label, callbacks in self.__start_resume_callbacks.items():
            for callback in callbacks:
                self.__launch_thread("start_resume", label, callback)
        with self.__send_tag_update_thread_lock:
            if not self.__is_running:
                self.__is_running = True
                self.__tag_update_thread = Thread(
                    target=self.__send_tag_messages_thread)
                self.__tag_update_thread.start()

    def __do_stop_pause(self) -> None:
        with self.__send_tag_update_thread_lock:
            self.__is_running = False
            self.__send_tag_update_thread_lock.notify_all()
        for label, callbacks in self.__pause_stop_callbacks.items():
            for callback in callbacks:
                self.__launch_thread("pause_stop", label, callback)
        if self.__tag_update_thread is not None:
            self.__tag_update_thread.join()
            self.__tag_update_thread = None

    def __send_tag_messages_thread(self) -> None:
        if self.__receiver_connection is None:
            return
        with self.__send_tag_update_thread_lock:
            while self.__is_running:
                self.__send_tag_update_thread_lock.wait(timeout=10.0)
                if self.__is_running:
                    self.__send_tag_messages_now()

    def __send_tag_messages_now(self) -> None:
        if self.__receiver_connection is None:
            return
        rc = (cast(SpallocEIEIOListener, self.__receiver_connection)
              if _is_spalloc_eieio(self.__receiver_connection) else None)
        for (x, y, tag, board_address) in self.__receiver_details:
            with self.__expect_scp_response_lock:
                self.__scp_response_received = None
                self.__expect_scp_response = True
                while self.__scp_response_received is None:
                    if rc:
                        rc.update_tag(x, y, tag, do_receive=False)
                        # No port trigger necessary; proxied already
                    else:
                        reprogram_tag_to_listener(
                            self.__receiver_connection, x, y, board_address,
                            tag, read_response=False)
                    self.__expect_scp_response_lock.wait(timeout=2.0)

    def __handle_scp_packet(self, data: bytes) -> bool:
        with self.__expect_scp_response_lock:
            # SCP unexpected
            if not self.__expect_scp_response:
                return False

            if (len(data) == _SCP_OK_SIZE and
                    data[_SCP_FLAGS_BYTE] == _SCP_RESPONSE_FLAGS and
                    data[_SCP_DEST_CPU_BYTE] == _SCP_RESPONSE_DEST):
                self.__scp_response_received = data
                self.__expect_scp_response = False
                self.__expect_scp_response_lock.notify_all()
                return True
            return False

    def __do_receive_packet(self, data: bytes) -> None:
        if self.__handle_scp_packet(data):
            return

        logger.debug("Received packet")
        try:
            header = _ONE_SHORT.unpack_from(data)[0]
            if header & 0xC000 == 0x4000:
                read_eieio_command_message(data, 0)
                return
            packet: EIEIODataMessage = read_eieio_data_message(data, 0)
            if packet.eieio_header.is_time:
                self.__handle_time_packet(packet)
            else:
                self.__handle_no_time_packet(packet)

        # pylint: disable=broad-except
        except Exception:
            logger.warning("problem handling received packet", exc_info=True)

    def __rcv_label(self, label_id: int) -> str:
        if self.__receive_labels is None:
            raise ConfigurationException("no receive labels defined")
        return self.__receive_labels[label_id]

    def __handle_time_packet(self, packet: EIEIODataMessage) -> None:
        key_times_labels: Dict[int, Dict[int, List[int]]] = defaultdict(
            lambda: defaultdict(list))
        atoms_times_labels: Dict[int, Dict[int, List[int]]] = defaultdict(
            lambda: defaultdict(list))

        while packet.is_next_element:
            element = packet.next_element
            if not isinstance(element, KeyPayloadDataElement):
                continue
            time = element.payload
            key = element.key
            if key in self.__key_to_atom_id_and_label:
                atom_id, label_id = self.__key_to_atom_id_and_label[key]
                key_times_labels[time][label_id].append(key)
                atoms_times_labels[time][label_id].append(atom_id)
            else:
                self.__handle_unknown_key(key)

        for time in key_times_labels:
            for label_id in key_times_labels[time]:
                label = self.__rcv_label(label_id)
                callbacks = self.__time_event_callbacks[label_id]
                if len(callbacks) == 0:
                    msg = f"LiveEventConnection received a packet " \
                          f"with time for {label} but has no callback. " \
                          f"Use add_receive_callback to register one."
                    warn_once(logger, msg)
                for c_back, use_atom in callbacks:
                    if use_atom:
                        c_back(label, time, atoms_times_labels[time][label_id])
                    else:
                        c_back(label, time, key_times_labels[time][label_id])

    def __handle_no_time_packet(self, packet: EIEIODataMessage) -> None:
        while packet.is_next_element:
            element = packet.next_element
            if not isinstance(element, (
                    KeyDataElement, KeyPayloadDataElement)):
                continue
            key = element.key
            if key in self.__key_to_atom_id_and_label:
                atom_id, label_id = self.__key_to_atom_id_and_label[key]
                label = self.__rcv_label(label_id)
                callbacks = self.__no_time_event_callbacks[label_id]
                if len(callbacks) == 0:
                    msg = f"LiveEventConnection received a packet " \
                          f"without time for {label} but has no callback." \
                          f" Use add_receive_no_time_callback to register one"
                    warn_once(logger, msg)
                for live_event_callback, translate_key in callbacks:
                    if isinstance(element, KeyPayloadDataElement):
                        if translate_key:
                            live_event_callback(
                                label, atom_id, element.payload)
                        else:
                            live_event_callback(label, key, element.payload)
                    else:
                        if translate_key:
                            live_event_callback(label, atom_id, None)
                        else:
                            live_event_callback(label, key, None)
            else:
                self.__handle_unknown_key(key)

    def __handle_unknown_key(self, key: int) -> None:
        if key not in self.__error_keys:
            self.__error_keys.add(key)
            logger.warning("Received unexpected key {}", key)

    def send_event(self, label: str, atom_id: int,
                   send_full_keys: bool = False) -> None:
        """
        Send an event from a single atom.

        :param label:
            The label of the vertex from which the event will originate
        :param atom_id: The ID of the atom sending the event
        :param send_full_keys:
            Determines whether to send full 32-bit keys, getting the key for
            each atom from the database, or whether to send 16-bit atom IDs
            directly
        """
        self.send_events(label, [atom_id], send_full_keys)

    def send_events(self, label: str, atom_ids: List[int],
                    send_full_keys: bool = False) -> None:
        """
        Send a number of events.

        :param label:
            The label of the vertex from which the events will originate
        :param atom_ids: array-like of atom IDs sending events
        :param send_full_keys:
            Determines whether to send full 32-bit keys, getting the key for
            each atom from the database, or whether to send 16-bit atom IDs
            directly
        """
        max_keys = _MAX_HALF_KEYS_PER_PACKET
        msg_type = EIEIOType.KEY_16_BIT
        if send_full_keys:
            max_keys = _MAX_FULL_KEYS_PER_PACKET
            msg_type = EIEIOType.KEY_32_BIT

        pos = 0
        packets_sent = 0
        x, y, p, ip_address = self.__send_address_details[label]
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

            self._send(message, x, y, p, ip_address)
            packets_sent += 1
            if (packets_sent % _MAX_SEND_BEFORE_PAUSE == 0 and
                    pos < len(atom_ids)):
                sleep(0.1)

    def send_event_with_payload(
            self, label: str, atom_id: int, payload: int) -> None:
        """
        Send an event with a payload from a single atom.

        :param label:
            The label of the vertex from which the event will originate
        :param atom_id: The ID of the atom sending the event
        :param payload: The payload to send
        """
        self.send_events_with_payloads(label, [(atom_id, payload)])

    def send_events_with_payloads(
            self, label: str,
            atom_ids_and_payloads: List[Tuple[int, int]]) -> None:
        """
        Send a number of events with payloads.

        :param label:
            The label of the vertex from which the events will originate
        :param atom_ids_and_payloads:
            array-like of tuples of atom IDs sending events with their payloads
        """
        msg_type = EIEIOType.KEY_PAYLOAD_32_BIT
        max_keys = _MAX_FULL_KEYS_PAYLOADS_PER_PACKET
        pos = 0
        packets_sent = 0
        x, y, p, ip_address = self.__send_address_details[label]
        while pos < len(atom_ids_and_payloads):
            message = EIEIODataMessage.create(msg_type)
            events = 0
            while pos < len(atom_ids_and_payloads) and events < max_keys:
                key, payload = atom_ids_and_payloads[pos]
                key = self._atom_id_to_key[label][key]
                message.add_key_and_payload(key, payload)
                pos += 1
                events += 1

            self._send(message, x, y, p, ip_address)
            packets_sent += 1
            if (packets_sent % _MAX_SEND_BEFORE_PAUSE == 0 and
                    pos < len(atom_ids_and_payloads)):
                sleep(0.1)

    def send_eieio_message(
            self, message: AbstractEIEIOMessage, label: str) -> None:
        """
        Send an EIEIO message (using one-way the live input) to the
        vertex with the given label.

        :param message: The EIEIO message to send
        :param label: The label of the receiver machine vertex
        """
        target = self.__send_address_details[label]
        if target is None:
            return
        x, y, p, ip_address = target
        self._send(message, x, y, p, ip_address)

    def _send(self, message: AbstractEIEIOMessage, x: int, y: int, p: int,
              ip_address: str) -> None:
        """
        Send an EIEIO message to a particular core.

        :param message: The EIEIO message to send
        :param x: Destination chip X coordinate
        :param y: Destination chip Y coordinate
        :param p: Destination core number
        :param ip_address:
            What Ethernet-enabled chip to send via (or rather its IP address)
        """
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
        if self.__sender_connection is None:
            raise ConfigurationException("no sender connection available")
        self.__sender_connection.send_to(
            # Prefix padding: two empty bytes
            b'\0\0' + sdp_message.bytestring,
            (ip_address, SCP_SCAMP_PORT))

    def close(self) -> None:
        with self.__send_tag_update_thread_lock:
            self.__is_running = False
            self.__send_tag_update_thread_lock.notify_all()
        self.__handle_possible_rerun_state()
        super().close()
