# spinnman imports
from spinnman import exceptions
from spinnman.messages.eieio.command_messages.eieio_command_header \
    import EIEIOCommandHeader
from spinnman.connections.udp_packet_connections.udp_connection \
    import UDPConnection
from spinnman import constants

# FrontEndCommon imports
from spinn_front_end_common.utilities.database.database_reader \
    import DatabaseReader

# general imports
from threading import Thread
import traceback
import logging

logger = logging.getLogger(__name__)


class DatabaseConnection(UDPConnection, Thread):
    """ A connection from the toolchain which will be notified\
        when the database has been written, and can then respond when the\
        database has been read, and further wait for notification that the\
        simulation has started.
    """

    def __init__(self, start_resume_callback_function=None,
                 stop_pause_callback_function=None, local_host=None,
                 local_port=19999):
        """

        :param start_resume_callback_function: A function to be called when
                    the start message has been received.  This function should
                    not take any parameters or return anything.
        :type start_resume_callback_function: function() -> None
        :param local_host: Optional specification of the local hostname or\
                    ip address of the interface to listen on
        :type local_host: str
        :param local_port: Optional specification of the local port to listen\
                    on.  Must match the port that the toolchain will send the\
                    notification on (19999 by default)
        :type local_port: int
        """
        UDPConnection.__init__(
            self, local_host=local_host, local_port=local_port,
            remote_host=None, remote_port=None)
        Thread.__init__(
            self, name="SpyNNakerDatabaseConnection:{}:{}".format(
                self.local_ip_address, self.local_port))
        self._database_callback_functions = list()
        self._start_resume_callback_function = start_resume_callback_function
        self._pause_and_stop_callback_function = stop_pause_callback_function
        self._running = False
        self.daemon = True
        self.start()

    def add_database_callback(self, database_callback_function):
        """ Add a database callback to be called when the database is ready

        :param database_callback_function: A function to be called when the\
                    database message has been received.  This function should\
                    take a single parameter, which will be a DatabaseReader\
                    object.  Once the function returns, it will be assumed\
                    that the database has been read, and the return response\
                    will be sent.
        :type database_callback_function: function(\
                    :py:class:`spynnaker_external_devices.pyNN.connections.database_reader.DatabaseReader`)\
                    -> None
        """
        self._database_callback_functions.append(database_callback_function)

    def run(self):
        try:
            self._running = True
            logger.info(
                "{}:{} Waiting for message to indicate that the database"
                " is ready".format(self.local_ip_address, self.local_port))
            while self._running:

                data, address = self._retrieve_database_address()

                if data is not None:
                    # Read the read packet confirmation
                    logger.info("{}:{} Reading database".format(
                        self.local_ip_address, self.local_port))
                    database_path = str(data[2:])

                    # Call the callback
                    database_reader = DatabaseReader(database_path)
                    for database_callback in self._database_callback_functions:
                        database_callback(database_reader)
                    database_reader.close()

                    # Send the response
                    logger.info(
                        "Notifying the toolchain that the database has been"
                        " read")
                    self.send_to(EIEIOCommandHeader(1).bytestring, address)

                    # Wait for the start of the simulation
                    if self._start_resume_callback_function is not None:
                        logger.info(
                            "Waiting for message to indicate that the "
                            "simulation has started or resumed")
                        command_code = self.receive()
                        command_code = EIEIOCommandHeader.from_bytestring(
                            command_code, 0).command
                        if (command_code == constants.EIEIO_COMMAND_IDS.
                                START_RESUME_NOTIFICATION.value):
                            # Call the callback
                            self._start_resume_callback_function()
                        else:
                            raise exceptions.SpinnmanInvalidPacketException(
                                "command_code",
                                "expected a start resume command code now,"
                                " and did not receive it.")

                    if self._pause_and_stop_callback_function is not None:
                        logger.info(
                            "waiting for message to indicate that the "
                            "simulation has stopped/ paused")
                        command_code = self.receive()
                        command_code = EIEIOCommandHeader.from_bytestring(
                            command_code, 0).command
                        if (command_code == constants.EIEIO_COMMAND_IDS.
                                STOP_PAUSE_NOTIFICATION.value):
                            # Call the callback
                            self._pause_and_stop_callback_function()
                        else:
                            raise exceptions.SpinnmanInvalidPacketException(
                                "command_code",
                                "expected a pause and stop command code now,"
                                " and did not receive it.")

        except Exception as e:
            traceback.print_exc()
            raise exceptions.SpinnmanIOException(str(e))

    def _retrieve_database_address(self):
        try:
            data, address = self.receive_with_address(timeout=3)
            return data, address
        except exceptions.SpinnmanTimeoutException:
            return None, None
        except exceptions.SpinnmanIOException as e:
            raise e

    def close(self):
        self._running = False
        UDPConnection.close(self)
