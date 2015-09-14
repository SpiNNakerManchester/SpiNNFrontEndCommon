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


class Reload(object):
    """ Reload functions for reload scripts
    """

    def __init__(self, machine_name, version, reports_states, bmp_details,
                 down_chips, down_cores, number_of_boards, height, width,
                 auto_detect_bmp, enable_reinjection, app_id=30):
        self._spinnaker_interface = \
            FrontEndCommonInterfaceFunctions(reports_states, None, None)
        self._spinnaker_interface.setup_interfaces(
            machine_name, bmp_details, down_chips, down_cores,
            version, number_of_boards, width, height, False, False,
            auto_detect_bmp, enable_reinjection)
        self._app_id = app_id
        self._reports_states = reports_states
        self._total_processors = 0
        self._buffer_manager = None
        self._notification_protocol = None

    def reload_application_data(self, reload_application_data_items,
                                load_data=True):
        """

        :param reload_application_data_items:  the application data for each
        core which needs data to be reloaded to work
        :param load_data: a boolean which will not reload if set to false.
        :return: None
        """

        progress = ProgressBar(len(reload_application_data_items),
                               "Reloading Application Data")
        # fixme need to find a way to remove these private accesses (maybe
        # when the dsg in partitioned it will clear up)

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
        :param routing_tables: the routing tables which need to be reloaded
        for the application to run successfully
        :param app_id: the id used to distinquish this for other applications
        :return: None
        """
        self._spinnaker_interface.load_routing_tables(routing_tables, app_id)

    def reload_binaries(self, executable_targets, app_id=30):
        """

        :param executable_targets:the executable targets which needs to
        be loaded onto the machine
        :param app_id: the id used to distinquish this for other applications
        :return: None
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

    def restart(self, executable_targets, runtime, time_scaling,
                turn_off_machine=True, app_id=30):
        """
        :param executable_targets: the executable targets which needs to
        be loaded onto the machine
        :param runtime: the amount of time this application is expected to run
        for
        :param time_scaling: the time scale factor for timing purposes
        :param app_id: the id used to distinquish this for other applications
        :return: None
        """
        self._buffer_manager.load_initial_buffers()
        self._spinnaker_interface.\
            wait_for_cores_to_be_ready(executable_targets, app_id)
        self._execute_start_messages()
        self._spinnaker_interface.start_all_cores(executable_targets, app_id)
        self._spinnaker_interface.wait_for_execution_to_complete(
            executable_targets, app_id, runtime, time_scaling)
        if turn_off_machine:
            self._spinnaker_interface._txrx.power_off_machine()

    def enable_buffer_manager(self, buffered_placements, buffered_tags):
        """
        enables the buffer manager with the placements and buffered tags
        :param buffered_placements: the placements which contain buffered\
                    vertices
        :param buffered_tags: the tags which contain buffered vertices
        :return:
        """
        self._buffer_manager = BufferManager(
            buffered_placements, buffered_tags,
            self._spinnaker_interface._txrx,
            self._reports_states, None, None)
        for placement in buffered_placements.placements:
            self._buffer_manager.add_sender_vertex(placement.subvertex)

    def execute_notification_protocol_read_messages(
            self, socket_addresses, wait_for_confirmations, database_path):
        """
        writes the interface for sending confirmations for database readers
        :param socket_addresses: the socket-addresses of the devices which
        need to read the database
        :param wait_for_confirmations bool saying if we should wait for
        confirmations
        :param database_path the path to the database
        :return:
        """
        self._notification_protocol = NotificationProtocol(
            socket_addresses, wait_for_confirmations)
        self._notification_protocol.send_read_notification(database_path)

    def _execute_start_messages(self):
        """
        sends the start messages to the external devices which need them
        :return:
        """
        if self._notification_protocol is not None:
            self._notification_protocol.send_start_notification()
