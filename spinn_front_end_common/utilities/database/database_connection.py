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
        "_database_callback_functions",
        "_pause_and_stop_callback_function",
        "_running",
        "_start_resume_callback_function"]

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
            self.local_ip_address, self.local_port), target=self.run)
        self._database_callback_functions = list()
        self._start_resume_callback_function = start_resume_callback_function
        self._pause_and_stop_callback_function = stop_pause_callback_function
        self._running = False
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
        self._database_callback_functions.append(database_callback_function)

    def run(self):
        self._running = True
        logger.info(
            "{}:{} Waiting for message to indicate that the database is "
            "ready", self.local_ip_address, self.local_port)
        try:
            while self._running:
                data, address = self._retrieve_database_address()
                if data is not None:
                    self._process_message(address, data)
        except Exception as e:
            logger.error("Failure processing database callback",
                         exc_info=True)
            raise_from(SpinnmanIOException(str(e)), e)
        finally:
            self._running = False

    def _process_message(self, address, data):
        # Read the read packet confirmation
        logger.info("{}:{} Reading database",
                    self.local_ip_address, self.local_port)
        if len(data) > 2:
            database_path = data[2:].decode()

            # Call the callback
            database_reader = DatabaseReader(database_path)
            for database_callback in self._database_callback_functions:
                database_callback(database_reader)
            database_reader.close()
        else:
            logger.warning("Database path was empty - assuming no database")

        # Send the response
        logger.info("Notifying the toolchain that the database has been read")
        self._send_command(1, address)

        # Wait for the start of the simulation
        if self._start_resume_callback_function is not None:
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
            self._start_resume_callback_function()

        if self._pause_and_stop_callback_function is not None:
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
            self._pause_and_stop_callback_function()

    def _send_command(self, command, address):
        self.send_to(EIEIOCommandHeader(command).bytestring, address)

    def _receive_command(self):
        return EIEIOCommandHeader.from_bytestring(self.receive(), 0).command

    def _retrieve_database_address(self):
        try:
            return self.receive_with_address(timeout=3)
        except SpinnmanTimeoutException:
            return None, None

    def close(self):
        self._running = False
        UDPConnection.close(self)
