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

import bisect
import math
from typing import Dict, Iterable, List, Optional, Sequence
from spinnman.messages.eieio.command_messages import HostSendSequencedData
from spinnman.messages.eieio.data_messages import EIEIODataHeader
from spinnman.messages.eieio import EIEIOType
from spinnman.constants import UDP_MESSAGE_MAX_SIZE

_HEADER_SIZE = EIEIODataHeader.get_header_size(
    EIEIOType.KEY_32_BIT, is_payload_base=True)

# The number of bytes in each key to be sent
_N_BYTES_PER_KEY = EIEIOType.KEY_32_BIT.key_bytes

# The number of keys allowed (different from the actual number as there is
#  an additional header)
_N_KEYS_PER_MESSAGE = (UDP_MESSAGE_MAX_SIZE -
                       (HostSendSequencedData.get_min_packet_length() +
                        _HEADER_SIZE)) // _N_BYTES_PER_KEY


def get_n_bytes(n_keys: int) -> int:
    """
    :returns: The number of bytes used by a given number of keys.
    :param n_keys: The number of keys
    """
    # Get the total number of messages
    n_messages = int(math.ceil(float(n_keys) / _N_KEYS_PER_MESSAGE))

    # Add up the bytes
    return ((_HEADER_SIZE * n_messages) +
            (n_keys * _N_BYTES_PER_KEY))


class BufferedSendingRegion(object):
    """
    A set of keys to be sent at given timestamps for a given region of
    data.

    .. note::
        Keys must be added in timestamp order or else an
        exception will be raised.
    """

    __slots__ = (
        #: A dictionary of timestamp -> list of keys
        "_buffer",

        #: A list of timestamps
        "_timestamps",

        #: The current position in the list of timestamps
        "_current_timestamp_pos")

    def __init__(self) -> None:
        self._buffer: Dict[int, List[int]] = dict()
        self._timestamps: List[int] = list()
        self._current_timestamp_pos: int = 0

    def add_key(self, timestamp: int, key: int) -> None:
        """
        Add a key to be sent at a given time.

        :param timestamp: The time at which the key is to be sent
        :param key: The key to send
        """
        if timestamp not in self._buffer:
            bisect.insort(self._timestamps, timestamp)
            self._buffer[timestamp] = list()
        self._buffer[timestamp].append(key)

    def add_keys(self, timestamp: int, keys: Iterable[int]) -> None:
        """
        Add a set of keys to be sent at the given time.

        :param timestamp: The time at which the keys are to be sent
        :param keys: The keys to send
        """
        for key in keys:
            self.add_key(timestamp, key)

    @property
    def n_timestamps(self) -> int:
        """
        The number of timestamps available.
        """
        return len(self._timestamps)

    @property
    def timestamps(self) -> Sequence[int]:
        """
        The timestamps for which there are keys.
        """
        return self._timestamps

    def get_n_keys(self, timestamp: int) -> int:
        """
        :returns: The number of keys for a given timestamp.
        :param timestamp:
            the time stamp to check if there's still keys to transmit
        """
        if timestamp in self._buffer:
            return len(self._buffer[timestamp])
        return 0

    @property
    def is_next_timestamp(self) -> bool:
        """
        Whether the region is empty.

        True if the region is empty, false otherwise.
        """
        return self._current_timestamp_pos < len(self._timestamps)

    @property
    def next_timestamp(self) -> Optional[int]:
        """
        The next timestamp of the data to be sent,
            or `None` if no more data.
        """
        if self.is_next_timestamp:
            return self._timestamps[self._current_timestamp_pos]
        return None

    def is_next_key(self, timestamp: int) -> bool:
        """
        Determine if there is another key for the given timestamp.

        :param timestamp:
            the time stamp to check if there's still keys to transmit
        :returns:
            True if there is at least on key still to send for this timestamp.
        """
        if timestamp in self._buffer:
            return bool(self._buffer[timestamp])
        return False

    def next_key(self) -> int:
        """
        The next key to be sent.
        Only call if :py:meth:`is_next_key` returns True.

        :returns: The next key
        """
        next_timestamp = self.next_timestamp
        assert next_timestamp is not None
        keys = self._buffer[next_timestamp]
        key = keys.pop()
        if not keys:
            del self._buffer[next_timestamp]
            self._current_timestamp_pos += 1
        return key

    @property
    def current_timestamp(self) -> int:
        """
        The current timestamp in the iterator.
        """
        return self._current_timestamp_pos

    def rewind(self) -> None:
        """
        Rewind the buffer to initial position.
        """
        self._current_timestamp_pos = 0

    def clear(self) -> None:
        """
        Clears the buffer.
        """
        self._buffer = dict()
        self._timestamps = list()
        self._current_timestamp_pos = 0
