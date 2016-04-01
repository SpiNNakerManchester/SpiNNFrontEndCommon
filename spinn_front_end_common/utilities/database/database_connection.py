from spinnman.exceptions import SpinnmanIOException, SpinnmanTimeoutException
from spinnman.messages.eieio.command_messages.eieio_command_header \
    import EIEIOCommandHeader
from spinnman.connections.udp_packet_connections.udp_connection \
    import UDPConnection


from spinn_front_end_common.utilities.database.database_reader \
    import DatabaseReader

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

    def __init__(self, start_callback_function=None, local_host=None,
                 local_port=19999):
        """

        :param start_callback_function: A function to be called when the start\
                    message has been received.  This function should not take\
                    any parameters or return anything.
        :type start_callback_function: function() -> None
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
        Thread.__init__(self,
                        name="spynnaker database connection for {}:{}"
                        .format(local_host, local_port))
        self._database_callback_functions = list()
        self._start_callback_function = start_callback_function
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
                "Waiting for message to indicate that the database is ready")
            while self._running:

                data, address = self._retrieve_database_address()

                if data is not None:
                    # Read the read packet confirmation
                    logger.info("Reading database")
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
                    if self._start_callback_function is not None:
                        logger.info(
                            "Waiting for message to indicate that the "
                            "simulation has started")
                        self.receive()

                        # Call the callback
                        self._start_callback_function()

        except Exception as e:
            traceback.print_exc()
            raise SpinnmanIOException(str(e))

    def _retrieve_database_address(self):
        try:
            data, address = self.receive_with_address(timeout=3)
            return data, address
        except SpinnmanTimeoutException:
            return None, None
        except SpinnmanIOException as e:
            raise e

    def close(self):
        self._running = False
        UDPConnection.close(self)
