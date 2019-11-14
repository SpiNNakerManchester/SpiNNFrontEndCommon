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

import bisect
import math
from spinnman.messages.eieio.command_messages import HostSendSequencedData
from spinnman.messages.eieio.data_messages import EIEIODataHeader
from spinnman.messages.eieio import EIEIOType
from spinnman.constants import UDP_MESSAGE_MAX_SIZE

_HEADER_SIZE = EIEIODataHeader.get_header_size(
    EIEIOType.KEY_32_BIT, is_payload_base=True)

# The number of bytes in each key to be sent
_N_BYTES_PER_KEY = EIEIOType.KEY_32_BIT.key_bytes  # @UndefinedVariable

# The number of keys allowed (different from the actual number as there is
#  an additional header)
_N_KEYS_PER_MESSAGE = (UDP_MESSAGE_MAX_SIZE -
                       (HostSendSequencedData.get_min_packet_length() +
                        _HEADER_SIZE)) // _N_BYTES_PER_KEY


def get_n_bytes(n_keys):
    """ Get the number of bytes used by a given number of keys.

    :param n_keys: The number of keys
    :type n_keys: int
    """

    # Get the total number of messages
    n_messages = int(math.ceil(float(n_keys) / _N_KEYS_PER_MESSAGE))

    # Add up the bytes
    return ((_HEADER_SIZE * n_messages) +
            (n_keys * _N_BYTES_PER_KEY))


class BufferedSendingRegion(object):
    """ A set of keys to be sent at given timestamps for a given region of\
        data.  Note that keys must be added in timestamp order or else an\
        exception will be raised.
    """

    __slots__ = [
        #: A dictionary of timestamp -> list of keys
        "_buffer",

        #: A list of timestamps
        "_timestamps",

        #: The current position in the list of timestamps
        "_current_timestamp_pos"
    ]

    def __init__(self):
        self._buffer = dict()
        self._timestamps = list()
        self._current_timestamp_pos = 0

    def add_key(self, timestamp, key):
        """ Add a key to be sent at a given time.

        :param timestamp: The time at which the key is to be sent
        :type timestamp: int
        :param key: The key to send
        :type key: int
        """
        if timestamp not in self._buffer:
            bisect.insort(self._timestamps, timestamp)
            self._buffer[timestamp] = list()
        self._buffer[timestamp].append(key)

    def add_keys(self, timestamp, keys):
        """ Add a set of keys to be sent at the given time.

        :param timestamp: The time at which the keys are to be sent
        :type timestamp: int
        :param keys: The keys to send
        :type keys: iterable(int)
        """
        for key in keys:
            self.add_key(timestamp, key)

    @property
    def n_timestamps(self):
        """ The number of timestamps available.

        :rtype: int
        """
        return len(self._timestamps)

    @property
    def timestamps(self):
        """ The timestamps for which there are keys.

        :rtype: iterable(int)
        """
        return self._timestamps

    def get_n_keys(self, timestamp):
        """ Get the number of keys for a given timestamp.

        :param timestamp: \
            the time stamp to check if there's still keys to transmit
        """
        if timestamp in self._buffer:
            return len(self._buffer[timestamp])
        return 0

    @property
    def is_next_timestamp(self):
        """ Determines if the region is empty.
            True if the region is empty, false otherwise.

        :rtype: bool
        """
        return self._current_timestamp_pos < len(self._timestamps)

    @property
    def next_timestamp(self):
        """ The next timestamp of the data to be sent, or None if no more data.

        :rtype: int or None
        """
        if self.is_next_timestamp:
            return self._timestamps[self._current_timestamp_pos]
        return None

    def is_next_key(self, timestamp):
        """ Determine if there is another key for the given timestamp.

        :param timestamp: \
            the time stamp to check if there's still keys to transmit
        :rtype: bool
        """
        if timestamp in self._buffer:
            return bool(self._buffer[timestamp])
        return False

    @property
    def next_key(self):
        """ The next key to be sent.

        :rtype: int
        """
        next_timestamp = self.next_timestamp
        keys = self._buffer[next_timestamp]
        key = keys.pop()
        if not keys:
            del self._buffer[next_timestamp]
            self._current_timestamp_pos += 1
        return key

    @property
    def current_timestamp(self):
        """ The current timestamp in the iterator.
        """
        return self._current_timestamp_pos

    def rewind(self):
        """ Rewind the buffer to initial position.
        """
        self._current_timestamp_pos = 0

    def clear(self):
        """ Clears the buffer.
        """

        self._buffer = dict()
        self._timestamps = list()
        self._current_timestamp_pos = 0
