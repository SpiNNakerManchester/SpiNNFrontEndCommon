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
            n_bytes: int = None, get_sum: bool = False) -> int:
        offset = 0
        n_bytes_to_write = n_bytes
        if n_bytes is None:
            n_bytes_to_write = len(data)
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
            return 0
        np_data = numpy.array(data, dtype=uint8)
        np_sum = int(numpy.sum(np_data.view(uint32), dtype=uint32))
        return np_sum & _UNSIGNED_WORD
