from spinn_front_end_common.utilities import constants

import struct


class ChannelBufferState(object):
    def __init__(
            self, start_address, current_write, current_read, end_address,
            region_id, last_buffer_operation):
        self._start_address = start_address
        self._current_write = current_write
        self._current_read = current_read
        self._end_address = end_address
        self._region_id = region_id
        self._last_buffer_operation = last_buffer_operation

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
    def last_buffer_operation(self):
        return self._last_buffer_operation

    @staticmethod
    def create_from_bytearray(data, offset):
        start_address, current_write, current_read, end_address,\
            region_id, last_buffer_operation = struct.unpack_from(
                "<IIIIBB", data, offset)[0]
        if last_buffer_operation == 0:
            last_buffer_operation = \
                constants.BUFFERING_OPERATIONS.BUFFER_READ.value
        else:
            last_buffer_operation = \
                constants.BUFFERING_OPERATIONS.BUFFER_WRITE.value
        buffer_state = ChannelBufferState(
            start_address, current_write, current_read, end_address,
            region_id, last_buffer_operation)
        return buffer_state, offset + 20
