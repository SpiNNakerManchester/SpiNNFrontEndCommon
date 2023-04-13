# Copyright (c) 2015 The University of Manchester
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

import logging
from concurrent.futures import ThreadPoolExecutor, wait  # @UnresolvedImport
from spinn_utilities.abstract_context_manager import AbstractContextManager
from spinn_utilities.config_holder import get_config_bool, get_config_int
from spinn_utilities.log import FormatAdapter
from spinnman.connections.udp_packet_connections import EIEIOConnection
from spinnman.messages.eieio.command_messages import (
    NotificationProtocolDatabaseLocation, NotificationProtocolPauseStop,
    NotificationProtocolStartResume)
from spinnman.exceptions import SpinnmanTimeoutException
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.constants import (
    MAX_DATABASE_PATH_LENGTH)
from spinn_front_end_common.utilities.exceptions import ConfigurationException

logger = FormatAdapter(logging.getLogger(__name__))


class NotificationProtocol(AbstractContextManager):
    """
    The protocol which hand shakes with external devices about the
    database and starting execution.

    The messages sent by this are received by instances of
    :py:class:`DatabaseConnection` (and its subclasses). They are not routed
    via SpiNNaker.
    """
    __slots__ = [
        "__database_message_connections",
        "__sent_visualisation_confirmation",
        "__wait_for_read_confirmation",
        "__wait_for_read_timeout",
        "__wait_futures",
        "__wait_pool"]

    def __init__(self):
        # Determines whether to wait for confirmation that the database
        # has been read before starting the simulation
        self.__wait_for_read_confirmation = get_config_bool(
            "Database", "wait_on_confirmation")
        self.__wait_for_read_timeout = get_config_int(
            "Database", "wait_on_confirmation_timeout")
        self.__wait_pool = ThreadPoolExecutor(max_workers=1)
        self.__wait_futures = list()
        self.__sent_visualisation_confirmation = False
        # These connections are not used to talk to SpiNNaker boards
        # but rather to code running on the current host computer
        self.__database_message_connections = [
            EIEIOConnection(
                local_port=socket_address.listen_port,
                remote_host=socket_address.notify_host_name,
                remote_port=socket_address.notify_port_no)
            for socket_address in
            FecDataView.iterate_database_socket_addresses()]

    def wait_for_confirmation(self):
        """
        If asked to wait for confirmation, waits for all external systems
        to confirm that they are configured and have read the database.
        """
        if self.__wait_for_read_confirmation:
            logger.info("** Awaiting for a response from an external source "
                        "to state its ready for the simulation to start **")
            results = wait(self.__wait_futures,
                           timeout=self.__wait_for_read_timeout)
            if results.not_done:
                raise SpinnmanTimeoutException(
                    f"waiting for external sources: {results.not_done}",
                    self.__wait_for_read_timeout)
        self.__wait_futures = list()

    def send_start_resume_notification(self):
        """
        Either waits till all sources have confirmed read the database
        and are configured, and/or just sends the start notification
        (when the system is executing).
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
        """
        Sends the pause / stop notifications when the script has either
        finished or paused.
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
    def send_read_notification(self):
        """
        Sends notifications to all devices which have expressed an
        interest in when the database has been written
        """
        notification_task = self.__wait_pool.submit(
            self._send_read_notification)
        if self.__wait_for_read_confirmation:
            self.__wait_futures.append(notification_task)

    def _send_read_notification(self):
        """
        Sends notifications to a list of socket addresses that the
        database has been written. Message also includes the path to the
        database

        :param str database_path: the path to the database
        """
        # noinspection PyBroadException
        try:
            self.__do_read_notify()
        except Exception:  # pylint: disable=broad-except
            logger.warning("problem when sending DB notification",
                           exc_info=True)

    def __do_read_notify(self):
        database_path = FecDataView.get_database_file_path()
        # add file path to database into command message.
        if (database_path is not None and
                len(database_path) > MAX_DATABASE_PATH_LENGTH):
            raise ConfigurationException(
                "The file path to the database is too large to be transmitted "
                "via the command packet, please set the file path manually "
                "and set the .cfg parameter [Database] send_file_path to "
                "False")
        message = NotificationProtocolDatabaseLocation(database_path)

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

        self.__sent_visualisation_confirmation = True

        # if the system needs to wait, try receiving a packet back
        if self.__wait_for_read_confirmation:
            for c in self.__database_message_connections:
                try:
                    c.receive_eieio_message()
                    logger.info(
                        "** Confirmation from {}:{} received, continuing **",
                        c.remote_ip_address, c.remote_port)
                except Exception:  # pylint: disable=broad-except
                    logger.warning(
                        "*** Failed to receive notification from external "
                        "application on {}:{} about the database ***",
                        c.remote_ip_address, c.remote_port, exc_info=True)

    @property
    def sent_visualisation_confirmation(self):
        """
        Whether the external application has actually been notified yet.

        :rtype: bool
        """
        return self.__sent_visualisation_confirmation

    def close(self):
        """
        Closes the thread pool and the connections.
        """
        if self.__wait_pool:
            self.__wait_pool.shutdown()
            self.__wait_futures = list()
            self.__wait_pool = None
        for c in self.__database_message_connections:
            c.close()
