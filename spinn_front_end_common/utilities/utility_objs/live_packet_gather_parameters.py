class LivePacketGatherParameters(object):
    """ Parameter holder for LPGs so that they can be instantiated at a\
        later date.
    """

    __slots__ = [
        '_port', '_hostname', "_tag", "_board_address", "_strip_sdp",
        "_use_prefix", "_key_prefix", "_prefix_type", "_message_type",
        "_right_shift", "_payload_as_time_stamps", "_use_payload_prefix",
        "_payload_prefix",  "_payload_right_shift",
        "_number_of_packets_sent_per_time_step", "_label", "_partition_id"
    ]

    def __init__(
            self, port, hostname, tag, board_address, strip_sdp, use_prefix,
            key_prefix, prefix_type, message_type, right_shift,
            payload_as_time_stamps, use_payload_prefix, payload_prefix,
            payload_right_shift, number_of_packets_sent_per_time_step,
            partition_id):
        # pylint: disable=too-many-arguments, too-many-locals
        self._port = port
        self._hostname = hostname
        self._tag = tag
        self._board_address = board_address
        self._strip_sdp = strip_sdp
        self._use_prefix = use_prefix
        self._key_prefix = key_prefix
        self._prefix_type = prefix_type
        self._message_type = message_type
        self._right_shift = right_shift
        self._payload_as_time_stamps = payload_as_time_stamps
        self._use_payload_prefix = use_payload_prefix
        self._payload_prefix = payload_prefix
        self._payload_right_shift = payload_right_shift
        self._number_of_packets_sent_per_time_step = \
            number_of_packets_sent_per_time_step
        self._partition_id = partition_id

    @property
    def port(self):
        return self._port

    @property
    def hostname(self):
        return self._hostname

    @property
    def tag(self):
        return self._tag

    @property
    def board_address(self):
        return self._board_address

    @property
    def strip_sdp(self):
        return self._strip_sdp

    @property
    def use_prefix(self):
        return self._use_prefix

    @property
    def key_prefix(self):
        return self._key_prefix

    @property
    def prefix_type(self):
        return self._prefix_type

    @property
    def message_type(self):
        return self._message_type

    @property
    def right_shift(self):
        return self._right_shift

    @property
    def payload_as_time_stamps(self):
        return self._payload_as_time_stamps

    @property
    def use_payload_prefix(self):
        return self._use_payload_prefix

    @property
    def payload_prefix(self):
        return self._payload_prefix

    @property
    def payload_right_shift(self):
        return self._payload_right_shift

    @property
    def number_of_packets_sent_per_time_step(self):
        return self._number_of_packets_sent_per_time_step

    @property
    def partition_id(self):
        return self._partition_id

    def __eq__(self, other):
        return (self._port == other.port and
                self._hostname == other.hostname and
                self._tag == other.tag and
                self._board_address == other.board_address and
                self._strip_sdp == other.strip_sdp and
                self._use_prefix == other.use_prefix and
                self._key_prefix == other.key_prefix and
                self._prefix_type == other.prefix_type and
                self._message_type == other.message_type and
                self._right_shift == other.right_shift and
                self._payload_as_time_stamps ==
                other.payload_as_time_stamps and
                self._use_payload_prefix == other.use_payload_prefix and
                self._payload_prefix == other.payload_prefix and
                self._payload_right_shift == other.payload_right_shift and
                self._number_of_packets_sent_per_time_step ==
                other.number_of_packets_sent_per_time_step and
                self._partition_id == other.partition_id)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        data = (
            self._port, self._tag, self._board_address, self._strip_sdp,
            self._use_prefix, self._key_prefix, self._prefix_type,
            self._message_type, self._right_shift,
            self._payload_as_time_stamps, self._use_payload_prefix,
            self._payload_prefix, self._payload_right_shift,
            self._number_of_packets_sent_per_time_step, self._partition_id)
        return hash(data)
