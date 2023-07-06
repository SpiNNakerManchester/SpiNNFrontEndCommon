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

import unittest
import struct
from spinn_machine import CoreSubsets, CoreSubset
from spinnman.processes import RoundRobinConnectionSelector
from spinnman.messages.sdp import SDPHeader
from spinnman.model.enums import SDP_RUNNING_MESSAGE_CODES
from spinnman.connections.udp_packet_connections import SCAMPConnection
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.utilities.scp import ClearIOBUFProcess
from fec_integration_tests.mock_machine import MockMachine


class TestIOBufClearProcess(unittest.TestCase):

    def setUp(self):
        unittest_setup()

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
