from threading import Thread
import traceback
from collections import OrderedDict

from spinn_front_end_common.utilities.database.database_connection \
    import DatabaseConnection

from spinnman.messages.eieio.data_messages.eieio_16bit\
    .eieio_16bit_data_message import EIEIO16BitDataMessage
from spinnman.messages.eieio.data_messages.eieio_32bit\
    .eieio_32bit_data_message import EIEIO32BitDataMessage
from spinnman.connections.connection_listener import ConnectionListener
from spinnman.connections.udp_packet_connections.udp_eieio_connection \
    import UDPEIEIOConnection


# The maximum number of 32-bit keys that will fit in a packet
_MAX_FULL_KEYS_PER_PACKET = 63

# The maximum number of 16-bit keys that will fit in a packet
_MAX_HALF_KEYS_PER_PACKET = 127


class LiveEventConnection(DatabaseConnection):
    """ A connection for receiving and sending live events from and to\
        SpiNNaker
    """

    def __init__(self, live_packet_gather_label, receive_labels=None,
                 send_labels=None, local_host=None, local_port=19999):
        """

        :param event_receiver_label: The label of the LivePacketGather\
                    vertex to which received events are being sent
        :param receive_labels: Labels of vertices from which live events\
                    will be received.
        :type receive_labels: iterable of str
        :param send_labels: Labels of vertices to which live events will be\
                    sent
        :type send_labels: iterable of str
        :param local_host: Optional specification of the local hostname or\
                    ip address of the interface to listen on
        :type local_host: str
        :param local_port: Optional specification of the local port to listen\
                    on.  Must match the port that the toolchain will send the\
                    notification on (19999 by default)
        :type local_port: int

        """

        DatabaseConnection.__init__(
            self, self._start_callback,
            local_host=local_host, local_port=local_port)

        self.add_database_callback(self._read_database_callback)

        self._live_packet_gather_label = live_packet_gather_label
        self._receive_labels = receive_labels
        self._send_labels = send_labels
        self._sender_connection = None
        self._send_address_details = dict()
        self._atom_id_to_key = dict()
        self._key_to_atom_id_and_label = dict()
        self._live_event_callbacks = list()
        self._start_callbacks = dict()
        self._init_callbacks = dict()
        if receive_labels is not None:
            for label in receive_labels:
                self._live_event_callbacks.append(list())
                self._start_callbacks[label] = list()
                self._init_callbacks[label] = list()
        if send_labels is not None:
            for label in send_labels:
                self._start_callbacks[label] = list()
                self._init_callbacks[label] = list()

    def add_init_callback(self, label, init_callback):
        """ Add a callback to be called to initialise a vertex

        :param label: The label of the vertex to be notified about. Must\
                    be one of the vertices listed in the constructor
        :type label: str
        :param init_callback: A function to be called to initialise the\
                    vertex.  This should take as parameters the label of the\
                    vertex, the number of neurons in the population,\
                    the run time of the simulation in milliseconds, and the\
                    simulation timestep in milliseconds
        :type init_callback: function(str, int, float, float) -> None
        """
        self._init_callbacks[label].append(init_callback)

    def add_receive_callback(self, label, live_event_callback):
        """ Add a callback for the reception of live events from a vertex

        :param label: The label of the vertex to be notified about. Must\
                    be one of the vertices listed in the constructor
        :type label: str
        :param live_event_callback: A function to be called when events\
                    are received.  This should take as parameters the label\
                    of the vertex, the simulation timestep when the event\
                    occurred, and an array-like of atom ids.
        :type live_event_callback: function(str, int, [int]) -> None
        """
        label_id = self._receive_labels.index(label)
        self._live_event_callbacks[label_id].append(live_event_callback)

    def add_start_callback(self, label, start_callback):
        """ Add a callback for the start of the simulation

        :param start_callback: A function to be called when the start\
                    message has been received.  This function should take the\
                    label of the referenced vertex, and an instance of\
                    this class, which can be used to send events
        :type start_callback: function(str, \
                    :py:class:`SpynnakerLiveEventConnection`) -> None
        :param label: the label of the function to be sent
        :type label: str
        """
        self._start_callbacks[label].append(start_callback)

    def _read_database_callback(self, database_reader):
        vertex_sizes = OrderedDict()
        run_time_ms = database_reader.get_configuration_parameter_value(
            "runtime")
        machine_timestep_ms = \
            database_reader.get_configuration_parameter_value(
                "machine_time_step") / 1000.0

        if self._send_labels is not None:
            self._sender_connection = UDPEIEIOConnection()
            for send_label in self._send_labels:
                ip_address, port = database_reader.get_live_input_details(
                    send_label)
                self._send_address_details[send_label] = (ip_address, port)
                self._atom_id_to_key[send_label] = \
                    database_reader.get_atom_id_to_key_mapping(send_label)
                vertex_sizes[send_label] = len(
                    self._atom_id_to_key[send_label])

        if self._receive_labels is not None:
            receivers = dict()
            listeners = dict()

            label_id = 0
            for receive_label in self._receive_labels:
                _, port, strip_sdp = database_reader.get_live_output_details(
                    receive_label, self._live_packet_gather_label)
                if strip_sdp:
                    if port not in receivers:
                        receiver = UDPEIEIOConnection(local_port=port)
                        listener = ConnectionListener(receiver)
                        listener.add_callback(self._receive_packet_callback)
                        listener.start()
                        receivers[port] = receiver
                        listeners[port] = listener
                else:
                    raise Exception("Currently, only ip tags which strip the"
                                    " SDP headers are supported")

                key_to_atom_id = \
                    database_reader.get_key_to_atom_id_mapping(receive_label)
                for (key, atom_id) in key_to_atom_id.iteritems():
                    self._key_to_atom_id_and_label[key] = (
                        atom_id, label_id)
                label_id += 1
                vertex_sizes[receive_label] = len(key_to_atom_id)

        for (label, vertex_size) in vertex_sizes.iteritems():
            for init_callback in self._init_callbacks[label]:
                init_callback(
                    label, vertex_size, run_time_ms, machine_timestep_ms)

    def _start_callback(self):
        for (label, callbacks) in self._start_callbacks.iteritems():
            for callback in callbacks:
                callback_thread = Thread(
                    target=callback, args=(label, self),
                    verbose=True,
                    name="start callback thread for live_event_connection"
                         "{}:{}".format(
                             self._local_port, self._local_ip_address))
                callback_thread.start()

    def _receive_packet_callback(self, packet):
        try:
            header = packet.eieio_header
            if not header.is_time:
                raise Exception(
                    "Only packets with a timestamp are currently considered")

            key_times_labels = OrderedDict()
            while packet.is_next_element:
                element = packet.next_element
                time = element.payload
                key = element.key
                if key in self._key_to_atom_id_and_label:
                    (atom_id, label_id) = \
                        self._key_to_atom_id_and_label[key]
                    if time not in key_times_labels:
                        key_times_labels[time] = dict()
                    if label_id not in key_times_labels[time]:
                        key_times_labels[time][label_id] = list()
                    key_times_labels[time][label_id].append(atom_id)

            for time in key_times_labels.iterkeys():
                for label_id in key_times_labels[time].iterkeys():
                    label = self._receive_labels[label_id]
                    for callback in self._live_event_callbacks[label_id]:
                        callback(label, time, key_times_labels[time][label_id])
        except:
            traceback.print_exc()

    def send_event(self, label, atom_id, send_full_keys=False):
        """ Send an event from a single atom

        :param label: The label of the vertex from which the event will\
                    originate
        :type label: str
        :param atom_id: The id of the atom sending the event
        :type atom_id: int
        :param send_full_keys: Determines whether to send full 32-bit keys,\
                    getting the key for each atom from the database, or\
                    whether to send 16-bit atom ids directly
        :type send_full_keys: bool
        """
        self.send_events(label, [atom_id], send_full_keys)

    def send_events(self, label, atom_ids, send_full_keys=False):
        """ Send a number of events

        :param label: The label of the vertex from which the events will\
                    originate
        :type label: str
        :param atom_ids: array-like of atom ids sending events
        :type atom_ids: [int]
        :param send_full_keys: Determines whether to send full 32-bit keys,\
                    getting the key for each atom from the database, or\
                    whether to send 16-bit atom ids directly
        :type send_full_keys: bool
        """
        max_keys = _MAX_HALF_KEYS_PER_PACKET
        if send_full_keys:
            max_keys = _MAX_FULL_KEYS_PER_PACKET

        pos = 0
        while pos < len(atom_ids):

            if send_full_keys:
                message = EIEIO32BitDataMessage()
            else:
                message = EIEIO16BitDataMessage()

            events_in_packet = 0
            while pos < len(atom_ids) and events_in_packet < max_keys:
                key = atom_ids[pos]
                if send_full_keys:
                    key = self._atom_id_to_key[label][key]
                message.add_key(key)
                pos += 1
                events_in_packet += 1
            ip_address, port = self._send_address_details[label]
            self._sender_connection.send_eieio_message_to(
                message, ip_address, port)
