"""
NotificationProtocol
"""

# spinnman imports
from multiprocessing.pool import ThreadPool
from spinnman.connections.udp_packet_connections.\
    eieio_command_connection import EieioCommandConnection
from spinnman.messages.eieio.command_messages.database_confirmation import \
    DatabaseConfirmation

# front end common imports
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities import exceptions

import logging
import traceback


logger = logging.getLogger(__name__)


class NotificationProtocol(object):
    """
    NotificationProtocol: the protocol which hand shakes with external devices
    about the database and starting execution
    """

    def __init__(self, socket_addresses, wait_for_read_confirmation):
        self._socket_addresses = socket_addresses
        # Determines whether to wait for confirmation that the database
        # has been read before starting the simulation
        self._wait_for_read_confirmation = wait_for_read_confirmation
        self._wait_pool = ThreadPool(processes=1)

    def _send_notification(self, database_path):
        data_base_message_connections = list()
        for socket_address in self._socket_addresses:
            data_base_message_connection = EieioCommandConnection(
                socket_address.listen_port, socket_address.notify_host_name,
                socket_address.notify_port_no)
            data_base_message_connections.append(data_base_message_connection)

        # add file path to database into command message.
        number_of_chars = len(database_path)
        if number_of_chars > constants.MAX_DATABASE_PATH_LENGTH:
            raise exceptions.ConfigurationException(
                "The file path to the database is too large to be "
                "transmitted via the command packet, "
                "please set the file path manually and "
                "set the .cfg parameter [Database] send_file_path "
                "to False")
        eieio_command_message = DatabaseConfirmation(database_path)

        # Send command and wait for response
        logger.info("*** Notifying visualiser that the database is ready ***")
        # noinspection PyBroadException
        try:
            for connection in data_base_message_connections:
                connection.send_eieio_command_message(eieio_command_message)

            # if the system needs to wait, try recieving a packet back
            if self._wait_for_read_confirmation:
                for connection in data_base_message_connections:
                    connection.receive_eieio_command_message()
            logger.info("*** Confirmation received, continuing ***")
        except Exception:
            logger.warning("*** Failed to notify external application about"
                           " the database - continuing ***")

    def wait_for_confirmation(self):
        """

        :return:
        """
        self._wait_pool.close()
        self._wait_pool.join()

    def send_start_notification(self):
        """

        :return:
        """
        data_base_message_connections = list()
        for socket_address in self._socket_addresses:
            data_base_message_connection = EieioCommandConnection(
                socket_address.listen_port,
                socket_address.notify_host_name,
                socket_address.notify_port_no)
            data_base_message_connections.append(
                data_base_message_connection)

        eieio_command_message = DatabaseConfirmation()
        for connection in data_base_message_connections:
            connection.send_eieio_command_message(eieio_command_message)

    # noinspection PyPep8
    def send_read_notification(self, database_path):
        """
        sends notifications to all devices which have expressed an interest in
        when the databse has been written
        :param database_path: the path to the database file
        :return:
        """
        self._wait_pool.apply_async(self._send_read_notification,
                                    args=[database_path])

    def _send_read_notification(self, database_path):
        # noinspection PyBroadException
        try:
            self._sent_visualisation_confirmation = True
            self._send_notification(database_path)
        except Exception:
            traceback.print_exc()

    def close(self):
        """
        closes the thread pool
        :return:
        """
        self._wait_pool.close()

