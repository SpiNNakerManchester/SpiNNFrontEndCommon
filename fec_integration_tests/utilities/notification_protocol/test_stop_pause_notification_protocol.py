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
from spinn_utilities.socket_address import SocketAddress
from spinnman.connections.udp_packet_connections import EIEIOConnection
from spinnman.messages.eieio.command_messages import EIEIOCommandMessage
from spinnman.constants import EIEIO_COMMAND_IDS
from spinn_front_end_common.utilities.notification_protocol import (
    NotificationProtocol)


class TestStopPauseNotificationProtocol(unittest.TestCase):

    def test_send_stop_pause_notification(self):
        """ Test the sending of the stop/pause message of the notification\
            protocol
        """
        listener = EIEIOConnection()
        socket_addresses = [SocketAddress(
            "127.0.0.1", listener.local_port, None)]
        protocol = NotificationProtocol(socket_addresses, False)
        protocol.send_stop_pause_notification()
        message = listener.receive_eieio_message(timeout=10)
        self.assertIsInstance(message, EIEIOCommandMessage)
        self.assertEqual(
            message.eieio_header.command,
            EIEIO_COMMAND_IDS.STOP_PAUSE_NOTIFICATION.value)


if __name__ == '__main__':
    unittest.main()
