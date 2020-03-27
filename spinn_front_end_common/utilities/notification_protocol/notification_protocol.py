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
from concurrent.futures import ThreadPoolExecutor, wait
from spinn_utilities.log import FormatAdapter
from spinnman.connections.udp_packet_connections import EIEIOConnection
from spinnman.messages.eieio.command_messages import (
    DatabaseConfirmation, NotificationProtocolPauseStop,
    NotificationProtocolStartResume)
from spinn_front_end_common.utilities.constants import (
    MAX_DATABASE_PATH_LENGTH)
from spinn_front_end_common.utilities.exceptions import ConfigurationException

logger = FormatAdapter(logging.getLogger(__name__))


class NotificationProtocol(object):
    """ The protocol which hand shakes with external devices about the\
        database and starting execution
    """
    __slots__ = [
        "__database_message_connections",
        "_sent_visualisation_confirmation",
        "__socket_addresses",
        "__wait_for_read_confirmation",
        "__wait_futures",
        "__wait_pool"]

    def __init__(self, socket_addresses, wait_for_read_confirmation):
        """
        :param list(~spinn_utilities.socket_address.SocketAddress) \
                socket_addresses: Where to notify.
        :param bool wait_for_read_confirmation:
            Whether to wait for the other side to acknowledge
        """
        self.__socket_addresses = socket_addresses

        # Determines whether to wait for confirmation that the database
        # has been read before starting the simulation
        self.__wait_for_read_confirmation = wait_for_read_confirmation
        self.__wait_pool = ThreadPoolExecutor(max_workers=1)
        self.__wait_futures = list()
        self._sent_visualisation_confirmation = False
        self.__database_message_connections = list()
        for socket_address in socket_addresses:
            self.__database_message_connections.append(EIEIOConnection(
                local_port=socket_address.listen_port,
                remote_host=socket_address.notify_host_name,
                remote_port=socket_address.notify_port_no))

    def wait_for_confirmation(self):
        """ If asked to wait for confirmation, waits for all external systems\
            to confirm that they are configured and have read the database

        :rtype: None
        """
        if self.__wait_for_read_confirmation:
            logger.info("** Awaiting for a response from an external source "
                        "to state its ready for the simulation to start **")
            wait(self.__wait_futures)
        self.__wait_futures = list()

    def send_start_resume_notification(self):
        """ Either waits till all sources have confirmed read the database\
            and are configured, and/or just sends the start notification\
            (when the system is executing)

        :rtype: None
        """
        logger.info("** Sending start / resume message to external sources "
                    "to state the simulation has started or resumed. **")
        if self.__wait_for_read_confirmation:
            self.wait_for_confirmation()
        eieio_command_message = NotificationProtocolStartResume()
        for c in self.__database_message_connections:
            try:
                c.send_eieio_message(eieio_command_message)
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    "*** Failed to send start/resume notification to external "
                    "application on {}:{} about the simulation ***",
                    c.remote_ip_address, c.remote_port, exc_info=True)

    def send_stop_pause_notification(self):
        """ Sends the pause / stop notifications when the script has either\
            finished or paused

        :rtype: None
        """
        logger.info("** Sending pause / stop message to external sources "
                    "to state the simulation has been paused or stopped. **")
        eieio_command_message = NotificationProtocolPauseStop()
        for c in self.__database_message_connections:
            try:
                c.send_eieio_message(eieio_command_message)
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    "*** Failed to send stop/pause notification to external "
                    "application on {}:{} about the simulation ***",
                    c.remote_ip_address, c.remote_port, exc_info=True)

    # noinspection PyPep8
    def send_read_notification(self, database_path):
        """ Sends notifications to all devices which have expressed an\
            interest in when the database has been written

        :param str database_path: the path to the database file
        """
        notification_thread = self.__wait_pool.submit(
                self._send_read_notification, database_path)
        if self.__wait_for_read_confirmation:
            self.__wait_futures.append(notification_thread)

    def _send_read_notification(self, database_path):
        """ Sends notifications to a list of socket addresses that the\
            database has been written. Message also includes the path to the\
            database

        :param str database_path: the path to the database
        """
        # noinspection PyBroadException
        try:
            self._do_read_notify(database_path)
        except Exception:  # pylint: disable=broad-except
            logger.warning("problem when sending DB notification",
                           exc_info=True)

    def _do_read_notify(self, database_path):
        self._sent_visualisation_confirmation = True

        # add file path to database into command message.
        if (database_path is not None and
                len(database_path) > MAX_DATABASE_PATH_LENGTH):
            raise ConfigurationException(
                "The file path to the database is too large to be transmitted "
                "via the command packet, please set the file path manually "
                "and set the .cfg parameter [Database] send_file_path to "
                "False")
        message = DatabaseConfirmation(database_path)

        # Send command and wait for response
        logger.info(
            "** Notifying external sources that the database is ready for "
            "reading **")

        # noinspection PyBroadException
        for c in self.__database_message_connections:
            try:
                c.send_eieio_message(message)
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    "*** Failed to notify external application on {}:{} "
                    "about the database ***",
                    c.remote_ip_address, c.remote_port, exc_info=True)

        # if the system needs to wait, try receiving a packet back
        for c in self.__database_message_connections:
            try:
                if self.__wait_for_read_confirmation:
                    c.receive_eieio_message()
                    logger.info(
                        "** Confirmation from {}:{} received, continuing **",
                        c.remote_ip_address, c.remote_port)
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    "*** Failed to receive notification from external "
                    "application on {}:{} about the database ***",
                    c.remote_ip_address, c.remote_port, exc_info=True)

    def close(self):
        """ Closes the thread pool
        """
        if self.__wait_pool:
            self.__wait_pool.shutdown()
            self.__wait_futures = list()
            self.__wait_pool = None
