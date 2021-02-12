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
from spinn_front_end_common.utilities.notification_protocol import (
    NotificationProtocol)


class CreateNotificationProtocol(object):
    """ Builds the notification protocol for GUI and external device \
        interaction.
    """

    __slots__ = []

    def __call__(
            self, wait_for_read_confirmation,
            socket_addresses, database_file_path):
        """
        :param bool wait_for_read_confirmation:
        :param socket_addresses: Where to notify.
        :type socket_addresses:
            list(~spinn_utilities.socket_address.SocketAddress)
        :param str database_file_path:
        """
        notification_protocol = NotificationProtocol(
            socket_addresses, wait_for_read_confirmation)
        notification_protocol.send_read_notification(database_file_path)
        return notification_protocol
