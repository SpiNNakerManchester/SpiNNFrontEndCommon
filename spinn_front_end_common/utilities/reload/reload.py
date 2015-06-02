"""
reload script for loading onto a amchien wtihout going through the mapper
"""
from spinn_front_end_common.interface.buffer_management.buffer_manager import \
    BufferManager
from spinn_front_end_common.interface.front_end_common_interface_functions \
    import FrontEndCommonInterfaceFunctions
from spinn_front_end_common.utilities.notification_protocol\
    .notification_protocol import NotificationProtocol

from spinnman.data.file_data_reader import FileDataReader

from pacman.utilities.progress_bar import ProgressBar
from pacman.model.routing_tables.multicast_routing_tables import \
    MulticastRoutingTables


class Reload(object):
    """ Reload functions for reload scripts
    """

    def __init__(self, machine_name, version, reports_states, app_id=30):
        self._spinnaker_interface = \
            FrontEndCommonInterfaceFunctions(reports_states, None, None)
        self._spinnaker_interface.setup_interfaces(
            machine_name, False, None, None, None, None, None, version)
        self._app_id = app_id
        self._reports_states = reports_states
        self._total_processors = 0
        self._buffer_manager = None

    def reload_application_data(self, reload_application_data_items,
                                load_data=True):
        """

        :param reload_application_data_items:
        :param load_data:
        :return:
        """

        progress = ProgressBar(len(reload_application_data_items),
                               "Reloading Application Data")
        for reload_application_data in reload_application_data_items:
            if load_data:
                data_file = FileDataReader(reload_application_data.data_file)
                self._spinnaker_interface._txrx.write_memory(
                    reload_application_data.chip_x,
                    reload_application_data.chip_y,
                    reload_application_data.base_address, data_file,
                    reload_application_data.data_size)
                data_file.close()
            user_0_register_address = self._spinnaker_interface._txrx.\
                get_user_0_register_address_from_core(
                    reload_application_data.chip_x,
                    reload_application_data.chip_y,
                    reload_application_data.processor_id)
            self._spinnaker_interface._txrx.write_memory(
                reload_application_data.chip_x, reload_application_data.chip_y,
                user_0_register_address, reload_application_data.base_address)
            progress.update()
            self._total_processors += 1
        progress.end()

    def reload_routes(self, routing_tables, app_id=30):
        """
        reloads a set of routing tables
        :param reload_routing_tables:
        :param app_id:
        :return:
        """
        self._spinnaker_interface.load_routing_tables(routing_tables, app_id)

    def reload_binaries(self, executable_targets, app_id=30):
        """

        :param executable_targets:
        :param app_id:
        :return:
        """
        self._spinnaker_interface.load_executable_images(executable_targets,
                                                         app_id)

    def reload_tags(self, iptags, reverse_iptags):
        """
        reloads the tags required to get the simualtion exeucting
        :param iptags: the iptags from the preivous run
        :param reverse_iptags: the reverse iptags from the preivous run
        :return:
        """
        self._spinnaker_interface.load_iptags(iptags)
        self._spinnaker_interface.load_reverse_iptags(reverse_iptags)

    def restart(self, socket_addresses, executable_targets, runtime,
                time_scaling, app_id=30):
        """

        :param socket_addresses:
        :param executable_targets:
        :param runtime:
        :param time_scaling:
        :param app_id:
        :return:
        """
        self._buffer_manager.load_initial_buffers()
        self._spinnaker_interface.\
            wait_for_cores_to_be_ready(executable_targets, app_id)
        self._execute_start_messages(socket_addresses)
        self._spinnaker_interface.start_all_cores(executable_targets, app_id)
        self._spinnaker_interface.wait_for_execution_to_complete(
            executable_targets, app_id, runtime, time_scaling)

    def enable_buffer_manager(self, buffered_placements, buffered_tags,
                              application_folder_path):
        """
        enables the buffer manager with the placements and buffered tags
        :param buffered_placements: the placements which contain buffered vertices
        :param buffered_tags: the tags which contain buffered vertices
        :param application_folder_path: the application folder
        :return:
        """
        self._buffer_manager = BufferManager(
            buffered_placements, buffered_tags, self._spinnaker_interface._txrx,
            self._reports_states, application_folder_path, None)

    @staticmethod
    def execute_notification_protocol_read_messages(
            socket_addresses, wait_for_confirmations, database_path):
        """
        writes the interface for sending confirmations for database readers
        :param socket_addresses: the socket-addresses of the devices which
        need to read the database
        :param wait_for_confirmations bool saying if we should wait for
        confirmations
        :param database_path the path to the database
        :return:
        """
        notification_protocol = NotificationProtocol(socket_addresses,
                                                     wait_for_confirmations)
        notification_protocol.send_read_notification(database_path)

    @staticmethod
    def _execute_start_messages(socket_addresses):
        """

        :param socket_addresses: the socket-addresses of the devices which
        need to read the database, and thus can do with start
        :return:
        """
        notification_protocol = NotificationProtocol(socket_addresses, False)
        notification_protocol.send_start_notification()




