# spinnman imports
from multiprocessing.pool import ThreadPool
from spinnman.connections.udp_packet_connections import EIEIOConnection
from spinnman.messages.eieio.command_messages import DatabaseConfirmation
from spinn_utilities.log import FormatAdapter
from spinnman.messages.eieio.command_messages \
    import NotificationProtocolPauseStop, NotificationProtocolStartResume

# front end common imports
from spinn_front_end_common.utilities.constants \
    import MAX_DATABASE_PATH_LENGTH
from spinn_front_end_common.utilities.exceptions import ConfigurationException

import logging


logger = FormatAdapter(logging.getLogger(__name__))


class NotificationProtocol(object):
    """ The protocol which hand shakes with external devices about the\
        database and starting execution
    """

    def __init__(self, socket_addresses, wait_for_read_confirmation):
        self._socket_addresses = socket_addresses

        # Determines whether to wait for confirmation that the database
        # has been read before starting the simulation
        self._wait_for_read_confirmation = wait_for_read_confirmation
        self._wait_pool = ThreadPool(processes=1)
        self._data_base_message_connections = list()
        for socket_address in socket_addresses:
            self._data_base_message_connections.append(EIEIOConnection(
                local_port=socket_address.listen_port,
                remote_host=socket_address.notify_host_name,
                remote_port=socket_address.notify_port_no))

    def wait_for_confirmation(self):
        """ If asked to wait for confirmation, waits for all external systems\
            to confirm that they are configured and have read the database

        :rtype: None
        """
        logger.info("** Awaiting for a response from an external source "
                    "to state its ready for the simulation to start **")
        self._wait_pool.close()
        self._wait_pool.join()

    def send_start_resume_notification(self):
        """ Either waits till all sources have confirmed read the database\
            and are configured, and/or just sends the start notification\
            (when the system is executing)

        :rtype: None
        """
        logger.info("** Sending start / resume message to external sources "
                    "to state the simulation has started or resumed. **")
        if self._wait_for_read_confirmation:
            self.wait_for_confirmation()
        eieio_command_message = NotificationProtocolStartResume()
        for c in self._data_base_message_connections:
            try:
                c.send_eieio_message(eieio_command_message)
            except Exception:
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
        for c in self._data_base_message_connections:
            try:
                c.send_eieio_message(eieio_command_message)
            except Exception:
                logger.warning(
                    "*** Failed to send stop/pause notification to external "
                    "application on {}:{} about the simulation ***",
                    c.remote_ip_address, c.remote_port, exc_info=True)

    # noinspection PyPep8
    def send_read_notification(self, database_path):
        """ Sends notifications to all devices which have expressed an\
            interest in when the database has been written

        :param database_path: the path to the database file
        :rtype: None
        """
        if database_path is not None:
            self._wait_pool.apply_async(self._send_read_notification,
                                        args=[database_path])

    def _send_read_notification(self, database_path):
        """ Sends notifications to a list of socket addresses that the\
            database has been written. Message also includes the path to the\
            database

        :param database_path: the path to the database
        :rtype: None

        """
        # noinspection PyBroadException
        try:
            if database_path is not None:
                self._do_read_notify(database_path)
        except Exception:
            logger.warning("problem when sending DB notification",
                           exc_info=True)

    def _do_read_notify(self, database_path):
        self._sent_visualisation_confirmation = True

        # add file path to database into command message.
        number_of_chars = len(database_path)
        if number_of_chars > MAX_DATABASE_PATH_LENGTH:
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
        for c in self._data_base_message_connections:
            try:
                c.send_eieio_message(message)
            except Exception:
                logger.warning(
                    "*** Failed to notify external application on {}:{} "
                    "about the database ***",
                    c.remote_ip_address, c.remote_port, exc_info=True)

        # if the system needs to wait, try receiving a packet back
        for c in self._data_base_message_connections:
            try:
                if self._wait_for_read_confirmation:
                    c.receive_eieio_message()
                    logger.info(
                        "** Confirmation from {}:{} received, continuing **",
                        c.remote_ip_address, c.remote_port)
            except Exception:
                logger.warning(
                    "*** Failed to receive notification from external "
                    "application on {}:{} about the database ***",
                    c.remote_ip_address, c.remote_port, exc_info=True)

    def close(self):
        """ Closes the thread pool
        """
        self._wait_pool.close()
