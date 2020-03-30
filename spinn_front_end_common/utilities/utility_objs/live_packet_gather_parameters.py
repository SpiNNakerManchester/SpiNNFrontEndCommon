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

from spinnman.messages.eieio import EIEIOType, EIEIOPrefix
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from pacman.model.resources.iptag_resource import IPtagResource

_HAS_PAYLOAD = (EIEIOType.KEY_PAYLOAD_32_BIT, EIEIOType.KEY_PAYLOAD_16_BIT)
_NO_PAYLOAD = (EIEIOType.KEY_32_BIT, EIEIOType.KEY_16_BIT)
#: Used to identify tags involved with the live packet gatherer.
TRAFFIC_IDENTIFIER = "LPG_EVENT_STREAM"


class LivePacketGatherParameters(object):
    """ Parameter holder for LPGs so that they can be instantiated at a\
        later date.
    """

    __slots__ = [
        '_port', '_hostname', "_tag", "_board_address", "_strip_sdp",
        "_use_prefix", "_key_prefix", "_prefix_type", "_message_type",
        "_right_shift", "_payload_as_time_stamps", "_use_payload_prefix",
        "_payload_prefix",  "_payload_right_shift",
        "_n_packets_per_time_step", "_label"
    ]

    def __init__(
            self, port=None, hostname=None, tag=None, strip_sdp=True,
            use_prefix=False, key_prefix=None, prefix_type=None,
            message_type=EIEIOType.KEY_32_BIT, right_shift=0,
            payload_as_time_stamps=True, use_payload_prefix=True,
            payload_prefix=None, payload_right_shift=0,
            number_of_packets_sent_per_time_step=0, label=None,
            board_address=None):
        """
        :raises ConfigurationException:
            If the parameters passed are known to be an invalid combination.
        """
        # pylint: disable=too-many-arguments, too-many-locals

        # Sanity checks
        if (message_type in _HAS_PAYLOAD and use_payload_prefix and
                payload_as_time_stamps):
            raise ConfigurationException(
                "Timestamp can either be included as payload prefix or as "
                "payload to each key, not both")
        if (message_type in _NO_PAYLOAD and not use_payload_prefix and
                payload_as_time_stamps):
            raise ConfigurationException(
                "Timestamp can either be included as payload prefix or as "
                "payload to each key, but current configuration does not "
                "specify either of these")
        if (prefix_type is not None and
                not isinstance(prefix_type, EIEIOPrefix)):
            raise ConfigurationException(
                "the type of a prefix type should be of a EIEIOPrefix, "
                "which can be located in: spinnman.messages.eieio")

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
        self._n_packets_per_time_step = number_of_packets_sent_per_time_step
        self._label = label

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
        return self._n_packets_per_time_step

    @property
    def label(self):
        return self._label

    def get_iptag_resource(self):
        """ Get a description of the IPtag that the LPG for these parameters \
            will require.

        :rtype: ~pacman.model.resources.IPtagResource
        """
        return IPtagResource(
            ip_address=self.hostname, port=self.port,
            strip_sdp=self.strip_sdp, tag=self.tag,
            traffic_identifier=TRAFFIC_IDENTIFIER)

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
                self._n_packets_per_time_step ==
                other.number_of_packets_sent_per_time_step and
                self._label == other.label)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        data = (
            self._port, self._tag, self._board_address, self._strip_sdp,
            self._use_prefix, self._key_prefix, self._prefix_type,
            self._message_type, self._right_shift,
            self._payload_as_time_stamps, self._use_payload_prefix,
            self._payload_prefix, self._payload_right_shift,
            self._n_packets_per_time_step, self._label)
        return hash(data)
