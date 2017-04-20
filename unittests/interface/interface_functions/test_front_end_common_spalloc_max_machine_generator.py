import unittest
import socket
from threading import Thread
import json
from spinn_front_end_common.interface.interface_functions\
    .front_end_common_spalloc_max_machine_generator \
    import FrontEndCommonSpallocMaxMachineGenerator


class _MockSpallocServer(Thread):

    def __init__(self, name, width, height, dead_boards, dead_links, tags):
        Thread.__init__(self)
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
        generator = FrontEndCommonSpallocMaxMachineGenerator()
        max_width, max_height, _, _ = generator.__call__(
            "localhost", server.port)
        self.assertEqual(max_width, 8)
        self.assertEqual(max_height, 8)

    def test_multiboard(self):
        server = _MockSpallocServer(
            "test", 1, 1, [], [], ["default"])
        server.start()
        generator = FrontEndCommonSpallocMaxMachineGenerator()
        max_width, max_height, _, _ = generator.__call__(
            "localhost", server.port)
        self.assertEqual(max_width, 12)
        self.assertEqual(max_height, 12)

    def test_specific_board(self):
        server = _MockSpallocServer(
            "test", 3, 2, [], [], ["test"])
        server.start()
        generator = FrontEndCommonSpallocMaxMachineGenerator()
        max_width, max_height, _, _ = generator.__call__(
            "localhost", server.port, "test")
        self.assertEqual(max_width, 12 * 3)
        self.assertEqual(max_height, 12 * 2)


if __name__ == "__main__":
    unittest.main()
