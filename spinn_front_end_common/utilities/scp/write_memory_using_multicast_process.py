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
from typing import Optional
import numpy
from numpy import uint8, uint32
from spinnman.constants import UDP_MESSAGE_MAX_SIZE
from spinnman.processes import AbstractMultiConnectionProcess
from spinnman.messages.scp.impl import CheckOKResponse
from spinn_front_end_common.utilities.utility_objs.\
    extra_monitor_scp_messages import SendMCDataMessage

_UNSIGNED_WORD = 0xFFFFFFFF


class WriteMemoryUsingMulticastProcess(
        AbstractMultiConnectionProcess[CheckOKResponse]):
    """
    How to send messages to write data using multicast
    """
    __slots__ = ()

    def write_memory_from_bytearray(
            self, x: int, y: int, p: int, target_x: int, target_y: int,
            base_address: int, data: bytes, data_offset: int = 0,
            n_bytes: Optional[int] = None, get_sum: bool = False) -> int:
        """
        Write memory using multicast over the advanced monitor connection.

        :param int x:
            The x-coordinate of the chip where the advanced monitor is
        :param int y:
            The y-coordinate of the chip where the advanced monitor is
        :param int p:
            The processor ID of the chip where the advanced monitor is
        :param int target_x:
            The x-coordinate of the chip where the memory is to be written to
        :param int target_y:
            The y-coordinate of the chip where the memory is to be written to
        :param int base_address:
            The address in SDRAM where the region of memory is to be written
        :param bytes data: The data to write.
        :param int n_bytes:
            The amount of data to be written in bytes.  If not specified,
            length of data is used.
        :param int data_offset: The offset from which the valid data begins
        :param bool get_sum: whether to return a checksum or 0
        :return: The number of bytes written, the checksum (0 if get_sum=False)
        :rtype: int, int
        """
        offset = 0
        if n_bytes is None:
            n_bytes_to_write = len(data)
        else:
            n_bytes_to_write = n_bytes
        with self._collect_responses():
            while n_bytes_to_write > 0:
                bytes_to_send = min(n_bytes_to_write, UDP_MESSAGE_MAX_SIZE)
                data_array = data[data_offset:data_offset + bytes_to_send]

                self._send_request(
                    SendMCDataMessage(x, y, p, target_x, target_y,
                                      base_address + offset, data_array))

                n_bytes_to_write -= bytes_to_send
                offset += bytes_to_send
                data_offset += bytes_to_send
        if not get_sum:
            return n_bytes, 0
        np_data = numpy.array(data, dtype=uint8)
        np_sum = int(numpy.sum(np_data.view(uint32), dtype=uint32))
        return n_bytes, np_sum & _UNSIGNED_WORD
