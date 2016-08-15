from spinn_front_end_common.utilities.notification_protocol.\
    notification_protocol import NotificationProtocol

import logging


logger = logging.getLogger(__name__)


class FrontEndCommonNotificationProtocol(object):
    """ The notification protocol for external device interaction
    """

    __slots__ = [
        # the notification protocol for talking to external devices
        "_notification_protocol"
    ]

    def __call__(
            self, wait_for_read_confirmation,
            socket_addresses, database_file_path):
        """

        :param wait_for_read_confirmation:
        :param socket_addresses:
        :param database_interface:
        :return:
        """

        # notification protocol
        self._notification_protocol = \
            NotificationProtocol(socket_addresses, wait_for_read_confirmation)
        self.send_read_notification(database_file_path)

        return self

    def wait_for_confirmation(self):
        """ Waits for devices to confirm they have read the database via the\
            notification protocol

        :return:
        """
        self._notification_protocol.wait_for_confirmation()

    def send_read_notification(self, database_directory):
        """ Send the read notifications via the notification protocol

        :param database_directory: the path to the database
        :return:
        """
        self._notification_protocol.send_read_notification(database_directory)

    def send_start_notification(self):
        """ Send the start notifications via the notification protocol

        :return:
        """
        self._notification_protocol.send_start_notification()

    def stop(self):
        """ Ends the notification protocol

        :return:
        """
        logger.debug("[data_base_thread] Stopping")
        self._notification_protocol.close()
