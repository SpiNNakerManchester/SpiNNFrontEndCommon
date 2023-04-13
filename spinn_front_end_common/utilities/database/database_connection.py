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
from threading import Thread
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
    """
    A connection from the toolchain which will be notified when the
    database has been written, and can then respond when the database
    has been read, and further wait for notification that the simulation
    has started.

    .. note::
        The machine description database reader can only be used while the
        registered database callbacks are running.

    .. note::
        This class coordinates with the :py:class:`NotificationProtocol` class
        without routing messages via SpiNNaker.
    """
    # This class must NOT be proxied! It does not handle messages from
    # SpiNNaker itself, but rather between the toolchain and any visualisation
    # tools plugged into it. The message it receives in __run() is sent by
    # NotificationProtocol._send_read_notification

    __slots__ = [
        "__database_callbacks",
        "__pause_and_stop_callback",
        "__running",
        "__start_resume_callback"]

    def __init__(self, start_resume_callback_function=None,
                 stop_pause_callback_function=None, local_host=None,
                 local_port=NOTIFY_PORT):
        """
        :param callable start_resume_callback_function:
            A function to be called when the start message has been received.
            This function should not take any parameters or return anything.
        :param str local_host:
            Optional specification of the local hostname or IP address of the
            interface to listen on
        :param int local_port:
            Optional specification of the local port to listen on. Must match
            the port that the toolchain will send the notification on (19999
            by default)
        """
        super().__init__(
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
        """
        Add a database callback to be called when the database is ready.

        :param callable(DatabaseReader,None) database_callback_function:
            A function to be called when the database message has been
            received.  This function should take a single parameter, which
            will be a DatabaseReader object. Once the function returns, it
            will be assumed that the database has been read and will not be
            needed further, and the return response will be sent.
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
                self.__process_run_cycle(timeout=3)
        except Exception as e:
            logger.error("Failure processing database callback",
                         exc_info=True)
            raise SpinnmanIOException(str(e)) from e
        finally:
            self.__running = False

    def __process_run_cycle(self, timeout):
        """
        Heart of :py:meth:`__run`.
        """
        # Wait to be told by the toolchain where the DB is located
        try:
            data, toolchain_address = self.receive_with_address(timeout)
        except (SpinnmanIOException, SpinnmanTimeoutException):
            return
        self.__read_db(toolchain_address, data)

        # Wait for the start of the simulation
        if self.__start_resume_callback is not None:
            self.__start_resume()

        # Wait for the end of the simulation
        if self.__pause_and_stop_callback is not None:
            self.__pause_stop()

    def __read_db(self, toolchain_address, data):
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
        self.__send_command(CMDS.DATABASE, toolchain_address)

    def __start_resume(self):
        logger.info(
            "Waiting for message to indicate that the simulation has "
            "started or resumed")
        command_code = self.__receive_command()
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
        command_code = self.__receive_command()
        if command_code != CMDS.STOP_PAUSE_NOTIFICATION.value:
            raise SpinnmanInvalidPacketException(
                "command_code",
                "expected a pause/stop command code now, and did not "
                "receive it")
        # Call the callback
        self.__pause_and_stop_callback()

    def __send_command(self, command, toolchain_address):
        self.send_to(EIEIOCommandHeader(command.value).bytestring,
                     toolchain_address)

    def __receive_command(self):
        return EIEIOCommandHeader.from_bytestring(self.receive(), 0).command

    def close(self):
        self.__running = False
        super().close()
