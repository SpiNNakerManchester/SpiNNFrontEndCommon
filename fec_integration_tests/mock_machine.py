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

from threading import Thread
from collections import deque
import struct
import traceback
from typing import Optional

from spinnman.messages.sdp import SDPMessage, SDPHeader, SDPFlag
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.enums import SCPResult
from spinnman.connections.udp_packet_connections import UDPConnection


class _SCPOKMessage(SDPMessage):

    def __init__(self, x: int, y: int, sequence: int):
        scp_header = SCPRequestHeader(
            command=SCPResult.RC_OK, sequence=sequence)
        sdp_header = SDPHeader(
            flags=SDPFlag.REPLY_NOT_EXPECTED, destination_port=0,
            destination_cpu=0, destination_chip_x=x, destination_chip_y=y)
        sdp_header.update_for_send(0, 0)
        super().__init__(sdp_header, data=scp_header.bytestring)


class MockMachine(Thread):
    """
    A Machine that can be used for testing protocol.
    """

    def __init__(self) -> None:
        super().__init__()

        # Set up a connection to be the machine
        self._receiver = UDPConnection()
        self._running = False
        self._messages: deque = deque()
        self._error: Optional[Exception] = None
        self._responses: deque = deque()

    @property
    def is_next_message(self) -> bool:
        return len(self._messages) > 0

    @property
    def next_message(self) -> bytes:
        return self._messages.popleft()

    @property
    def error(self) -> Optional[Exception]:
        return self._error

    @property
    def local_port(self) -> int:
        return self._receiver.local_port

    def _do_receive(self) -> None:
        data, address = self._receiver.receive_with_address()
        self._messages.append(data)
        sdp_header = SDPHeader.from_bytestring(data, 2)
        _result, sequence = struct.unpack_from("<2H", data, 10)
        if self._responses:
            response = self._responses.popleft()
            response._data = (
                response._data[:10] + struct.pack("<H", sequence) +
                response._data[12:])
        else:
            response = _SCPOKMessage(
                sdp_header.source_chip_x, sdp_header.source_chip_y,
                sequence)
        if response is not None:
            self._receiver.send_to(
                struct.pack("<2x") + response.bytestring, address)

    def run(self) -> None:
        self._running = True
        while self._running:
            try:
                if self._receiver.is_ready_to_receive(10):
                    self._do_receive()
            except Exception as e:  # pylint: disable=broad-except
                if self._running:
                    traceback.print_exc()
                    self._error = e

    def stop(self) -> None:
        self._running = False
        self._receiver.close()
