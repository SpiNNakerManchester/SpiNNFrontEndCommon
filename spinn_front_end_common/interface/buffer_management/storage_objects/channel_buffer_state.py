from spinn_front_end_common.utilities import constants

import struct


class ChannelBufferState(object):
    """ Stores information related to a single channel output\
        buffering state, as it is retrieved at the end of a simulation on the\
        SpiNNaker system.
    """

    __slots__ = [
        # start buffering area memory address (32 bits)
        "_start_address",

        # address where data was last written (32 bits)
        "_current_write",

        # address where data was last read (32 bits)
        "_current_read",

        # The address of first byte after the buffer (32 bits)
        "_end_address",

        # The id of the region (8 bits)
        "_region_id",

        # True if the region overflowed during the simulation (8 bits)
        "_missing_info",

        # Last operation performed on the buffer - read or write (8 bits)
        "_last_buffer_operation",

        #
        "_update_completed",
    ]

    def __init__(
            self, start_address, current_write, current_read, end_address,
            region_id, missing_info, last_buffer_operation):
        """

        :param start_address: start buffering area memory address (32 bits)
        :param current_write: address where data was last written (32 bits)
        :param current_read: address where data was last read (32 bits)
        :param end_address: The address of first byte after the buffer\
                (32 bits)
        :param region_id: The id of the region (8 bits)
        :param missing_info: True if the region overflowed during the\
                simulation (8 bits)
        :param last_buffer_operation: Last operation performed on the buffer\
                - read or write (8 bits)
        """
        self._start_address = start_address
        self._current_write = current_write
        self._current_read = current_read
        self._end_address = end_address
        self._region_id = region_id
        self._missing_info = missing_info
        self._last_buffer_operation = last_buffer_operation
        self._update_completed = False

    @property
    def start_address(self):
        return self._start_address

    @property
    def current_write(self):
        return self._current_write

    @property
    def current_read(self):
        return self._current_read

    @property
    def end_address(self):
        return self._end_address

    @property
    def region_id(self):
        return self._region_id

    @property
    def missing_info(self):
        return self._missing_info

    @property
    def last_buffer_operation(self):
        return self._last_buffer_operation

    @property
    def is_state_updated(self):
        return self._update_completed

    def update_last_operation(self, operation):
        self._last_buffer_operation = operation

    def update_read_pointer(self, read_ptr):
        self._current_read = read_ptr

    def set_update_completed(self):
        self._update_completed = True

    @staticmethod
    def create_from_bytearray(data):
        (start_address, current_write, current_read, end_address,
         region_id, missing_info, last_buffer_operation) = struct.unpack_from(
            "<IIIIBBBx", data)
        if last_buffer_operation == 0:
            last_buffer_operation = \
                constants.BUFFERING_OPERATIONS.BUFFER_READ.value
        else:
            last_buffer_operation = \
                constants.BUFFERING_OPERATIONS.BUFFER_WRITE.value
        buffer_state = ChannelBufferState(
            start_address, current_write, current_read, end_address,
            region_id, missing_info, last_buffer_operation)
        return buffer_state

    @staticmethod
    def size_of_channel_state():
        return 20
