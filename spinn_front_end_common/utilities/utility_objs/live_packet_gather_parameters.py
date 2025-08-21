# Copyright (c) 2017 The University of Manchester
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
from typing import Any, Optional
from spinnman.messages.eieio import EIEIOType, EIEIOPrefix
from pacman.model.resources.iptag_resource import IPtagResource
from spinn_front_end_common.utilities.exceptions import ConfigurationException

_HAS_PAYLOAD = (EIEIOType.KEY_PAYLOAD_32_BIT, EIEIOType.KEY_PAYLOAD_16_BIT)
_NO_PAYLOAD = (EIEIOType.KEY_32_BIT, EIEIOType.KEY_16_BIT)
#: Used to identify tags involved with the live packet gatherer.
TRAFFIC_IDENTIFIER = "LPG_EVENT_STREAM"


class LivePacketGatherParameters(object):
    """
    Parameter holder for :py:class:`LivePacketGather`\\ers so that they can be
    instantiated at a later date.
    """

    __slots__ = (
        '_port', '_hostname', "_tag", "_strip_sdp", "_use_prefix",
        "_key_prefix", "_prefix_type", "_message_type", "_right_shift",
        "_payload_as_time_stamps", "_use_payload_prefix", "_payload_prefix",
        "_payload_right_shift", "_n_packets_per_time_step", "_label",
        "_received_key_mask", "_translate_keys", "_translated_key_right_shift")

    def __init__(
            self, port: int, hostname: str, tag: Optional[int] = None,
            strip_sdp: bool = True, use_prefix: bool = False,
            key_prefix: Optional[int] = None,
            prefix_type: Optional[EIEIOPrefix] = None,
            message_type: EIEIOType = EIEIOType.KEY_32_BIT,
            right_shift: int = 0,
            payload_as_time_stamps: bool = True,
            use_payload_prefix: bool = True,
            payload_prefix: Optional[int] = None, payload_right_shift: int = 0,
            number_of_packets_sent_per_time_step: int = 0,
            label: Optional[str] = None,
            received_key_mask: int = 0xFFFFFFFF,
            translate_keys: bool = False,
            translated_key_right_shift: int = 0) -> None:
        """
        :raises ConfigurationException:
            If the parameters passed are known to be an invalid combination.
        """
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
        self._received_key_mask = received_key_mask
        self._translate_keys = translate_keys
        self._translated_key_right_shift = translated_key_right_shift

    @property
    def port(self) -> int:
        """
        Where to send data from SpiNNaker:
        the port of the listening UDP socket.
        """
        return self._port

    @property
    def hostname(self) -> str:
        """
        Where to send data from SpiNNaker: the host name of the listening UDP
        socket.
        """
        return self._hostname

    @property
    def tag(self) -> Optional[int]:
        """
        A fixed tag ID to assign, or `None` if any tag is OK
        """
        return self._tag

    @property
    def strip_sdp(self) -> bool:
        """
        Whether to remove SDP headers from the messages before sending.
        """
        return self._strip_sdp

    @property
    def use_prefix(self) -> bool:
        """
        Whether to use EIEIO prefix compaction on keys.
        """
        return self._use_prefix

    @property
    def key_prefix(self) -> Optional[int]:
        """
        The EIEIO key prefix to remove from messages.
        """
        return self._key_prefix

    @property
    def prefix_type(self) -> Optional[EIEIOPrefix]:
        """
        The type of prefix.
        """
        return self._prefix_type

    @property
    def message_type(self) -> EIEIOType:
        """
        The type of messages to send.
        """
        return self._message_type

    @property
    def right_shift(self) -> int:
        """
        Shift to apply to keys.
        """
        return self._right_shift

    @property
    def payload_as_time_stamps(self) -> bool:
        """
        Whether the payloads are timestamps.
        """
        return self._payload_as_time_stamps

    @property
    def use_payload_prefix(self) -> bool:
        """
        Whether to use prefix compaction for payloads.
        """
        return self._use_payload_prefix

    @property
    def payload_prefix(self) -> Optional[int]:
        """
        The payload prefix to remove if applying compaction.
        """
        return self._payload_prefix

    @property
    def payload_right_shift(self) -> int:
        """
        Shift to apply to payloads.
        """
        return self._payload_right_shift

    @property
    def number_of_packets_sent_per_time_step(self) -> int:
        """
        The maximum number of packets to send in a timestep.
        """
        return self._n_packets_per_time_step

    @property
    def label(self) -> Optional[str]:
        """
        A label.
        """
        return self._label

    @property
    def received_key_mask(self) -> int:
        """
        A mask to select which keys are dispatched.
        """
        return self._received_key_mask

    @property
    def translate_keys(self) -> bool:
        """
        Whether to apply translation to keys.
        """
        return self._translate_keys

    @property
    def translated_key_right_shift(self) -> int:
        """
        Shift to apply in key translation.
        """
        return self._translated_key_right_shift

    def get_iptag_resource(self) -> IPtagResource:
        """
        :returns: A description of the :py:class:`~spinn_machine.tags.IPTag`
           that the LPG for these parameters will require.
        """
        return IPtagResource(
            ip_address=self.hostname, port=self.port,
            strip_sdp=self.strip_sdp, tag=self.tag,
            traffic_identifier=TRAFFIC_IDENTIFIER)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, LivePacketGatherParameters):
            return False
        return (self._port == other.port and
                self._hostname == other.hostname and
                self._tag == other.tag and
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
                self._label == other.label and
                self._received_key_mask == other.received_key_mask and
                self._translate_keys == other.translate_keys and
                self._translated_key_right_shift ==
                other.translated_key_right_shift)

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        data = (
            self._port, self._tag, self._strip_sdp, self._use_prefix,
            self._key_prefix, self._prefix_type, self._message_type,
            self._right_shift, self._payload_as_time_stamps,
            self._use_payload_prefix, self._payload_prefix,
            self._payload_right_shift, self._n_packets_per_time_step,
            self._label, self._received_key_mask, self._translate_keys,
            self._translated_key_right_shift)
        return hash(data)
