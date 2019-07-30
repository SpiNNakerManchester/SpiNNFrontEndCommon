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

import logging
from spinn_front_end_common.utilities.notification_protocol import (
    NotificationProtocol as Notification)

logger = logging.getLogger(__name__)


class NotificationProtocol(object):
    """ The notification protocol for external device interaction
    """

    __slots__ = [
        # the notification protocol for talking to external devices
        "_notification_protocol"
    ]

    def __call__(
            self, wait_for_read_confirmation,
            socket_addresses, database_file_path):

        # notification protocol
        self._notification_protocol = Notification(
            socket_addresses, wait_for_read_confirmation)
        self.send_read_notification(database_file_path)

        return self

    def wait_for_confirmation(self):
        """ Waits for devices to confirm they have read the database via the\
            notification protocol

        :rtype: None:
        """
        self._notification_protocol.wait_for_confirmation()

    def send_read_notification(self, database_directory):
        """ Send the read notifications via the notification protocol

        :param database_directory: the path to the database
        :rtype: None:
        """
        self._notification_protocol.send_read_notification(database_directory)

    def send_start_resume_notification(self):
        """ Send the start notifications via the notification protocol

        :rtype: None:
        """
        self._notification_protocol.send_start_resume_notification()

    def send_stop_pause_notification(self):
        """ Send the stop or pause notifications via the notification protocol

        :rtype: None:
        """
        self._notification_protocol.send_stop_pause_notification()

    def stop(self):
        """ Ends the notification protocol

        :rtype: None:
        """
        logger.debug("[data_base_thread] Stopping")
        self._notification_protocol.close()
