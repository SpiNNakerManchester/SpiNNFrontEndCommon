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

import unittest
import socket
from threading import Thread
import json
from spinn_front_end_common.interface.interface_functions import (
    SpallocMaxMachineGenerator)


class _MockSpallocServer(Thread):

    def __init__(self, name, width, height, dead_boards, dead_links, tags):
        super(_MockSpallocServer, self).__init__()
        self._name = name
        self._width = width
        self._height = height
        self._dead_boards = dead_boards
        self._dead_links = dead_links
        self._tags = tags

        self._socket = socket.socket()
        self._socket.bind(("", 0))
        _, self._port = self._socket.getsockname()
        self._socket.listen(5)

    @property
    def port(self):
        return self._port

    def run(self):
        client, _ = self._socket.accept()
        data = b""
        while b"\n" not in data:
            data += client.recv(100)
        message = {"return": [{
            "name": self._name, "width": self._width, "height": self._height,
            "dead_boards": self._dead_boards, "dead_links": self._dead_links,
            "tags": self._tags}]}
        client.send(json.dumps(message).encode("utf-8") + b"\n")


class TestFrontEndCommonSpallocMaxMachineGenerator(unittest.TestCase):

    def test_single_board(self):
        server = _MockSpallocServer(
            "test", 1, 1, [(0, 0, 1), (0, 0, 2)], [], ["default"])
        server.start()
        generator = SpallocMaxMachineGenerator()
        machine = generator("localhost", server.port)
        self.assertEqual(machine.max_chip_x, 7)
        self.assertEqual(machine.max_chip_y, 7)

    def test_multiboard(self):
        server = _MockSpallocServer(
            "test", 1, 1, [], [], ["default"])
        server.start()
        generator = SpallocMaxMachineGenerator()
        machine = generator("localhost", server.port)
        self.assertEqual(machine.max_chip_x, 11)
        self.assertEqual(machine.max_chip_y, 11)

    def test_specific_board(self):
        server = _MockSpallocServer(
            "test", 3, 2, [], [], ["test"])
        server.start()
        generator = SpallocMaxMachineGenerator()
        machine = generator("localhost", server.port, "test")
        self.assertEqual(machine.max_chip_x, (12 * 3) - 1)
        self.assertEqual(machine.max_chip_y, (12 * 2) - 1)


if __name__ == "__main__":
    unittest.main()
