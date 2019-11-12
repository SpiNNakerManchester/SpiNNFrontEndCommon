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

import struct
from spinn_front_end_common.utilities.constants import (
    BUFFERING_OPERATIONS, BYTES_PER_WORD)

_CHANNEL_BUFFER_PATTERN = struct.Struct("<IIIIIBBBx")


class ChannelBufferState(object):
    """ Stores information related to a single channel output buffering\
        state, as it is retrieved at the end of a simulation on the\
        SpiNNaker system.
    """

    __slots__ = [
        #: start buffering area memory address (32 bits)
        "_start_address",

        #: address where data was last written (32 bits)
        "_current_write",

        #: address where the DMA write got up to (32 bits)
        "_current_dma_write",

        #: address where data was last read (32 bits)
        "_current_read",

        #: The address of first byte after the buffer (32 bits)
        "_end_address",

        #: The ID of the region (8 bits)
        "_region_id",

        #: True if the region overflowed during the simulation (8 bits)
        "_missing_info",

        #: Last operation performed on the buffer - read or write (8 bits)
        "_last_buffer_operation",

        #: bool check for if its extracted data from machine
        "_update_completed",
    ]

    #: 4 bytes for _start_address, 4 for _current_write,
    #: 4 for current_dma_write,
    #: 4 for _current_read, 4 for _end_address, 1 for _region_id,
    #: 1 for _missing_info, 1 for _last_buffer_operation
    ChannelBufferStateSize = 6 * BYTES_PER_WORD

    def __init__(
            self, start_address, current_write, current_dma_write,
            current_read, end_address, region_id, missing_info,
            last_buffer_operation):
        """
        :param start_address: start buffering area memory address (32 bits)
        :type start_address: int
        :param current_write: address where data was last written (32 bits)
        :type current_write: int
        :param current_read: address where data was last read (32 bits)
        :type current_read: int
        :param end_address: \
            The address of first byte after the buffer (32 bits)
        :type end_address: int
        :param region_id: The ID of the region (8 bits)
        :type region_id: int
        :param missing_info: \
            True if the region overflowed during the simulation (8 bits)
        :type missing_info: int
        :param last_buffer_operation: \
            Last operation performed on the buffer - read or write (8 bits)
        :type last_buffer_operation: int
        """
        # pylint: disable=too-many-arguments
        self._start_address = start_address
        self._current_write = current_write
        self._current_dma_write = current_dma_write
        self._current_read = current_read
        self._end_address = end_address
        self._region_id = region_id
        self._missing_info = missing_info
        self._last_buffer_operation = last_buffer_operation
        self._update_completed = False

    @property
    def start_address(self):
        """ start buffering area memory address """
        return self._start_address

    @property
    def current_write(self):
        """ address where data was last written """
        return self._current_write

    @property
    def current_read(self):
        """ address where data was last read """
        return self._current_read

    @property
    def end_address(self):
        """ The address of first byte after the buffer """
        return self._end_address

    @property
    def region_id(self):
        """ The ID of the region """
        return self._region_id

    @property
    def missing_info(self):
        """ True if the region overflowed during the simulation """
        return self._missing_info

    @property
    def last_buffer_operation(self):
        """ Last operation performed on the buffer - read (0) or write (non-0)
        """
        return self._last_buffer_operation

    @property
    def is_state_updated(self):
        """ bool check for if its extracted data from machine """
        return self._update_completed

    def update_last_operation(self, operation):
        self._last_buffer_operation = operation

    def update_read_pointer(self, read_ptr):
        self._current_read = read_ptr

    def set_update_completed(self):
        self._update_completed = True

    @staticmethod
    def create_from_bytearray(data):
        """
        :param data: The contents of the buffer state structure on SpiNNaker.
        :type data: bytearray
        :rtype: \
            ~spinn_front_end_common.interface.buffer_management.storage_objects.ChannelBufferState
        """
        (start_address, current_write, current_dma_write, current_read,
         end_address, region_id, missing_info, last_buffer_operation) = \
            _CHANNEL_BUFFER_PATTERN.unpack_from(data)
        if last_buffer_operation == 0:
            last_buffer_operation = BUFFERING_OPERATIONS.BUFFER_READ.value
        else:
            last_buffer_operation = BUFFERING_OPERATIONS.BUFFER_WRITE.value
        buffer_state = ChannelBufferState(
            start_address, current_write, current_dma_write, current_read,
            end_address, region_id, missing_info, last_buffer_operation)
        return buffer_state

    @staticmethod
    def size_of_channel_state():
        """
        :rtype: int
        """
        return ChannelBufferState.ChannelBufferStateSize
