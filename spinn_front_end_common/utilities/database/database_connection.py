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
from threading import Thread
from six import raise_from
from spinn_utilities.log import FormatAdapter
from spinnman.exceptions import (
    SpinnmanIOException, SpinnmanInvalidPacketException,
    SpinnmanTimeoutException)
from spinnman.messages.eieio.command_messages import EIEIOCommandHeader
from spinnman.connections.udp_packet_connections import UDPConnection
from spinnman.constants import EIEIO_COMMAND_IDS as CMDS
from spinn_front_end_common.utilities.constants import NOTIFY_PORT
from .database_reader import DatabaseReader

logger = FormatAdapter(logging.getLogger(__name__))


class DatabaseConnection(UDPConnection):
    """ A connection from the toolchain which will be notified when the \
        database has been written, and can then respond when the database \
        has been read, and further wait for notification that the simulation \
        has started.
    """

    __slots__ = [
        "__database_callbacks",
        "__pause_and_stop_callback",
        "__running",
        "__start_resume_callback"]

    def __init__(self, start_resume_callback_function=None,
                 stop_pause_callback_function=None, local_host=None,
                 local_port=NOTIFY_PORT):
        """
        :param start_resume_callback_function: A function to be called when \
            the start message has been received.  This function should not \
            take any parameters or return anything.
        :type start_resume_callback_function: function() -> None
        :param local_host: Optional specification of the local hostname or\
            IP address of the interface to listen on
        :type local_host: str
        :param local_port: Optional specification of the local port to listen \
            on.  Must match the port that the toolchain will send the \
            notification on (19999 by default)
        :type local_port: int
        """
        super(DatabaseConnection, self).__init__(
            local_host=local_host, local_port=local_port,
            remote_host=None, remote_port=None)
        thread = Thread(name="SpyNNakerDatabaseConnection:{}:{}".format(
            self.local_ip_address, self.local_port), target=self.__run)
        self.__database_callbacks = list()
        self.__start_resume_callback = start_resume_callback_function
        self.__pause_and_stop_callback = stop_pause_callback_function
        self.__running = False
        thread.daemon = True
        thread.start()

    def add_database_callback(self, database_callback_function):
        """ Add a database callback to be called when the database is ready.

        :param database_callback_function: A function to be called when the\
            database message has been received.  This function should take \
            a single parameter, which will be a DatabaseReader object. \
            Once the function returns, it will be assumed that the database \
            has been read, and the return response will be sent.
        :type database_callback_function: function(\
            :py:class:`spinn_front_end_common.utilities.database.database_reader.DatabaseReader`)\
            -> None
        :raises SpinnmanIOException: If anything goes wrong
        """
        self.__database_callbacks.append(database_callback_function)

    def __run(self):
        # pylint: disable=broad-except
        self.__running = True
        logger.info(
            "{}:{} Waiting for message to indicate that the database is "
            "ready", self.local_ip_address, self.local_port)
        try:
            while self.__running:
                try:
                    data, address = self.receive_with_address(timeout=3)
                except SpinnmanTimeoutException:
                    continue
                self.__read_db(address, data)

                # Wait for the start of the simulation
                if self.__start_resume_callback is not None:
                    self.__start_resume()

                # Wait for the end of the simulation
                if self.__pause_and_stop_callback is not None:
                    self.__pause_stop()
        except Exception as e:
            logger.error("Failure processing database callback",
                         exc_info=True)
            raise_from(SpinnmanIOException(str(e)), e)
        finally:
            self.__running = False

    def __read_db(self, address, data):
        # Read the read packet confirmation
        logger.info("{}:{} Reading database",
                    self.local_ip_address, self.local_port)
        if len(data) > 2:
            database_path = data[2:].decode('utf-8')
            logger.info("database is at {}", database_path)

            # Call the callback
            with DatabaseReader(database_path) as db_reader:
                for db_callback in self.__database_callbacks:
                    db_callback(db_reader)
        else:
            logger.warning("Database path was empty - assuming no database")

        # Send the response
        logger.info("Notifying the toolchain that the database has been read")
        self._send_command(CMDS.DATABASE_CONFIRMATION, address)

    def __start_resume(self):
        logger.info(
            "Waiting for message to indicate that the simulation has "
            "started or resumed")
        command_code = self._receive_command()
        if command_code != CMDS.START_RESUME_NOTIFICATION.value:
            raise SpinnmanInvalidPacketException(
                "command_code",
                "expected a start/resume command code now, and did not "
                "receive it")
        # Call the callback
        self.__start_resume_callback()

    def __pause_stop(self):
        logger.info(
            "Waiting for message to indicate that the simulation has "
            "stopped or paused")
        command_code = self._receive_command()
        if command_code != CMDS.STOP_PAUSE_NOTIFICATION.value:
            raise SpinnmanInvalidPacketException(
                "command_code",
                "expected a pause/stop command code now, and did not "
                "receive it")
        # Call the callback
        self.__pause_and_stop_callback()

    def _send_command(self, command, address):
        self.send_to(EIEIOCommandHeader(command.value).bytestring, address)

    def _receive_command(self):
        return EIEIOCommandHeader.from_bytestring(self.receive(), 0).command

    def close(self):
        self.__running = False
        UDPConnection.close(self)
