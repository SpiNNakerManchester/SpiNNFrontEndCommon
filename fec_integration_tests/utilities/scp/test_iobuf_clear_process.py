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
import struct
from spinn_machine import CoreSubsets, CoreSubset
from spinnman.processes import RoundRobinConnectionSelector
from spinnman.messages.sdp import SDPHeader
from spinnman.connections.udp_packet_connections import SCAMPConnection
from spinn_front_end_common.utilities.scp import ClearIOBUFProcess
from spinn_front_end_common.utilities.constants import (
    SDP_RUNNING_MESSAGE_CODES)
from fec_integration_tests.mock_machine import MockMachine


class TestIOBufClearProcess(unittest.TestCase):

    def test_clear_iobuf_process(self):
        receiver = MockMachine()
        receiver.start()

        # Set up a connection to the "machine"
        connection = SCAMPConnection(
            0, 0, remote_host="127.0.0.1", remote_port=receiver.local_port)
        selector = RoundRobinConnectionSelector([connection])

        # Create the process and run it
        process = ClearIOBUFProcess(selector)
        process.clear_iobuf(CoreSubsets([CoreSubset(0, 0, [1])]), 1)
        receiver.stop()

        # Check the message received
        self.assertTrue(receiver.is_next_message)
        data = receiver.next_message
        sdp_header = SDPHeader.from_bytestring(data, 2)
        self.assertEqual(sdp_header.destination_chip_x, 0)
        self.assertEqual(sdp_header.destination_chip_y, 0)
        self.assertEqual(sdp_header.destination_cpu, 1)
        command, = struct.unpack_from("<H", data, 10)
        self.assertEqual(
            command,
            SDP_RUNNING_MESSAGE_CODES.SDP_CLEAR_IOBUF_CODE.value)


if __name__ == "__main__":
    unittest.main()
