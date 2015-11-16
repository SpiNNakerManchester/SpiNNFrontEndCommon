"""
BufferedSendingRegion
"""

# The size of the header of a message
from spinnman.messages.eieio.command_messages.host_send_sequenced_data import \
    HostSendSequencedData
from spinnman.messages.eieio.data_messages.eieio_data_header import \
    EIEIODataHeader
from spinnman.messages.eieio.eieio_type import EIEIOType
from spinnman import constants
from spinnman.messages.eieio.command_messages.event_stop_request import \
    EventStopRequest

import bisect
import math


class BufferedSendingRegion(object):
    """ A set of keys to be sent at given timestamps for a given region of\
        data.  Note that keys must be added in timestamp order or else an\
        exception will be raised
    """

    _HEADER_SIZE = EIEIODataHeader.get_header_size(
        EIEIOType.KEY_32_BIT, is_payload_base=True)

    # The number of bytes in each key to be sent
    _N_BYTES_PER_KEY = EIEIOType.KEY_32_BIT.key_bytes

    # The number of keys allowed (different from the actual number as there is
    #  an additional header)
    _N_KEYS_PER_MESSAGE = (constants.UDP_MESSAGE_MAX_SIZE -
                           (HostSendSequencedData.get_min_packet_length() +
                            _HEADER_SIZE)) / _N_BYTES_PER_KEY

    def __init__(self, max_buffer_size):

        # A dictionary of timestamp -> list of keys
        self._buffer = dict()

        # A list of timestamps
        self._timestamps = list()

        # The current position in the list of timestamps
        self._current_timestamp_pos = 0

        self._buffer_size = None

        self._total_region_size = None

        self._max_size_of_buffer = max_buffer_size

    @property
    def buffer_size(self):
        """
        property method for getting the max size of this buffer
        :return:
        """
        if self._buffer_size is None:
            self._calculate_sizes()
        return self._buffer_size

    @property
    def total_region_size(self):
        """
        property methof for getting the max size of this region
        :return:
        """
        if self._total_region_size is None:
            self._calculate_sizes()
        return self._total_region_size

    @property
    def max_buffer_size_possible(self):
        """
        property method to return the max possible size of a buffer from this
        region
        :return:
        """
        return self._max_size_of_buffer

    def _calculate_sizes(self):
        """
        takes the data and deduces how much size the buffer and the region
        requires.
        :return:
        """
        size = 0
        for timestamp in self._timestamps:
            n_keys = self.get_n_keys(timestamp)
            size += self.get_n_bytes(n_keys)
        size += EventStopRequest.get_min_packet_length()
        if size > self._max_size_of_buffer:
            self._buffer_size = self._max_size_of_buffer
        else:
            self._buffer_size = size
        self._total_region_size = size

    def get_n_bytes(self, n_keys):
        """ Get the number of bytes used by a given number of keys

        :param n_keys: The number of keys
        :type n_keys: int
        """

        # Get the total number of messages
        n_messages = int(math.ceil(float(n_keys) / self._N_KEYS_PER_MESSAGE))

        # Add up the bytes
        return ((self._HEADER_SIZE * n_messages) +
                (n_keys * self._N_BYTES_PER_KEY))

    def add_key(self, timestamp, key):
        """ Add a key to be sent at a given time

        :param timestamp: The time at which the key is to be sent
        :type timestamp: int
        :param key: The key to send
        :type key: int
        """
        if timestamp not in self._buffer:
            bisect.insort(self._timestamps, timestamp)
            self._buffer[timestamp] = list()
        self._buffer[timestamp].append(key)
        self._total_region_size = None
        self._buffer_size = None

    def add_keys(self, timestamp, keys):
        """ Add a set of keys to be sent at the given time

        :param timestamp: The time at which the keys are to be sent
        :type timestamp: int
        :param keys: The keys to send
        :type keys: iterable of int
        """
        for key in keys:
            self.add_key(timestamp, key)

    @property
    def n_timestamps(self):
        """ The number of timestamps available

        :rtype: int
        """
        return len(self._timestamps)

    @property
    def timestamps(self):
        """ The timestamps for which there are keys

        :rtype: iterable of int
        """
        return self._timestamps

    def get_n_keys(self, timestamp):
        """ Get the number of keys for a given timestamp
        :param timestamp: the time stamp to check if theres still keys to
        transmit
        """
        if timestamp in self._buffer:
            return len(self._buffer[timestamp])
        return 0

    @property
    def is_next_timestamp(self):
        """ Determines if the region is empty
        :return: True if the region is empty, false otherwise
        :rtype: bool
        """
        return self._current_timestamp_pos < len(self._timestamps)

    @property
    def next_timestamp(self):
        """ The next timestamp of the data to be sent, or None if no more data

        :rtype: int or None
        """
        if self.is_next_timestamp:
            return self._timestamps[self._current_timestamp_pos]
        return None

    def is_next_key(self, timestamp):
        """ Determine if there is another key for the given timestamp
        :param timestamp: the time stamp to check if theres still keys to
        transmit
        :rtype: bool
        """
        if timestamp in self._buffer:
            return len(self._buffer[timestamp]) > 0
        return False

    @property
    def next_key(self):
        """ The next key to be sent

        :rtype: int
        """
        next_timestamp = self.next_timestamp
        keys = self._buffer[next_timestamp]
        key = keys.pop()
        if len(keys) == 0:
            del self._buffer[next_timestamp]
            self._current_timestamp_pos += 1
        return key

    @property
    def current_timestamp(self):
        """
        returns the current timestamp in the iterator
        :return:
        """
        return self._current_timestamp_pos

    def rewind(self):
        """
        Rewinds the buffer to initial position.
        :return:
        """
        self._current_timestamp_pos = 0
