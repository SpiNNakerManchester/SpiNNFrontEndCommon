# Copyright (c) 2017-2023 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_utilities.socket_address import SocketAddress
from spinnman.connections.udp_packet_connections import EIEIOConnection
from spinnman.messages.eieio.command_messages import EIEIOCommandMessage
from spinnman.constants import EIEIO_COMMAND_IDS
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.utilities.notification_protocol import (
    NotificationProtocol)


class TestStartResumeNotificationProtocol(unittest.TestCase):

    def setUp(self):
        unittest_setup()

    def test_send_start_resume_notification(self):
        """ Test the sending of the start/resume message of the notification\
            protocol
        """
        listener = EIEIOConnection()
        FecDataWriter.mock().add_database_socket_address(SocketAddress(
            "127.0.0.1", listener.local_port, None))
        protocol = NotificationProtocol()
        protocol.send_start_resume_notification()
        message = listener.receive_eieio_message(timeout=10)
        self.assertIsInstance(message, EIEIOCommandMessage)
        self.assertEqual(
            message.eieio_header.command,
            EIEIO_COMMAND_IDS.START_RESUME_NOTIFICATION.value)


if __name__ == '__main__':
    unittest.main()
