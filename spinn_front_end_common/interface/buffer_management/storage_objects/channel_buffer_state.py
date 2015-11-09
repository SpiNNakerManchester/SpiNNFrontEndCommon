from spinn_front_end_common.utilities import constants

import struct


class ChannelBufferState(object):
    """
    This class stores information related to a single channel output
    buffering state, as it is retrieved at the end of a simulation on the
    SpiNNaker system. The state contains, in order:
    1 - start buffering area memory address (32 bits)
    2 - current write pointer address, first space where to write data (32 bits)
    3 - current read pointer address, first space chere to read data (32 bits)
    4 - end buffering area memory address, first byte after the
    assigned memory area (32 bits)
    5 - application region identifier (8 bits)
    6 - bit to identify if the region overflowed during the simulation
    and therefore some information has not been transferred to the
    host - missing_info (8 bits)
    7 - Last operation performed on the buffer - read or write (8 bits)
    """
    def __init__(
            self, start_address, current_write, current_read, end_address,
            region_id, missing_info, last_buffer_operation):
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
    def create_from_bytearray(data, offset):
        start_address, current_write, current_read, end_address,\
            region_id, missing_info, last_buffer_operation = struct.unpack_from(
                "<IIIIBBBx", data, offset)
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