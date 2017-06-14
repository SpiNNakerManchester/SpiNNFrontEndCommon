import unittest

from spinn_front_end_common.utilities.notification_protocol\
    .notification_protocol import NotificationProtocol
from spinn_front_end_common.utilities.notification_protocol.socket_address \
    import SocketAddress

from spinnman.connections.udp_packet_connections.udp_eieio_connection \
    import UDPEIEIOConnection
from spinnman.messages.eieio.command_messages.eieio_command_message \
    import EIEIOCommandMessage
from spinnman import constants


class TestNotificationProtocol(unittest.TestCase):

    def test_send_start_resume_notification(self):
        """ Test the sending of the start/resume message of the notification\
            protocol
        """
        listener = UDPEIEIOConnection()
        socket_addresses = [SocketAddress(
            "127.0.0.1", listener.local_port, None)]
        protocol = NotificationProtocol(socket_addresses, False)
        protocol.send_start_resume_notification()
        message = listener.receive_eieio_message(timeout=10)
        self.assertIsInstance(message, EIEIOCommandMessage)
        self.assertEqual(
            message.eieio_header.command,
            constants.EIEIO_COMMAND_IDS.START_RESUME_NOTIFICATION.value)


if __name__ == '__main__':
    unittest.main()
