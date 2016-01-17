# front end common imports
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities import reload
from spinn_front_end_common.utilities.reload.reload_routing_table import \
    ReloadRoutingTable

# general imports
import os
import shutil


class ReloadScript(object):
    """ Generates a script for reloading a simulation
    """

    def __init__(
            self, binary_directory, hostname, board_version, bmp_details,
            down_chips, down_cores, number_of_boards, height, width,
            auto_detect_bmp, enable_reinjection, scamp_connection_data,
            boot_port_num, verify, executable_targets,
            wait_for_read_confirmation, database_file_path,
            runtime, time_scale_factor, send_start_notification,
            reset_machine_on_start_up, processor_to_app_data_base_address=None,
            placement_to_app_data_files=None, dsg_targets=None):
        self._binary_directory = binary_directory
        self._wait_on_confiramtion = None
        self._runtime = 0
        self._time_scale_factor = None
        if not self._binary_directory.endswith(os.sep):
            self._binary_directory += os.sep

        file_name = self._binary_directory + "rerun_script.py"
        shutil.copyfile(os.path.join(
            os.path.split(
                os.path.abspath(reload.__file__))[0],
            "rerun_script_template.py"),
            file_name)
        try:
            self._file = open(file_name, "a")
        except IOError:
            raise exceptions.SpinnFrontEndException(
                "Cannot open {} to write the rerun script".format(file_name))

        self._println("runtime = {}".format(runtime))
        self._println(
            "send_start_notification = {}".format(send_start_notification))
        self._println("reset_machine_on_start_up = {}"
                      .format(reset_machine_on_start_up))
        self._println("time_scale_factor = {}".format(time_scale_factor))
        self._println("machine_name = \"{}\"".format(hostname))
        self._println("machine_version = {}".format(board_version))
        self._println("bmp_details = \"{}\"".format(bmp_details))
        self._println("down_chips = \"{}\"".format(down_chips))
        self._println("down_cores = \"{}\"".format(down_cores))
        self._println("number_of_boards = {}".format(number_of_boards))
        self._println("height = {}".format(height))
        self._println("width = {}".format(width))
        self._println("auto_detect_bmp = {}".format(auto_detect_bmp))
        self._println("enable_reinjection = {}".format(enable_reinjection))
        self._println("placements = dict()")
        self._println("boot_port_num = {}".format(boot_port_num))

        if placement_to_app_data_files is not None:
            # Convert file paths to local file names
            local_placement_to_app_data_files = dict()
            if placement_to_app_data_files is not None:
                for (placement, file_paths) in \
                        placement_to_app_data_files.iteritems():
                    local_file_paths = list()
                    for file_path in file_paths:
                        local_file_path = os.path.basename(file_path)
                        local_file_paths.append(local_file_path)
                    local_placement_to_app_data_files[placement] = \
                        local_file_paths

            # Write them in the reload script
            self._println("placement_to_app_data_files = {}"
                          .format(local_placement_to_app_data_files))
        else:
            self._println("placement_to_app_data_files = None")

        if dsg_targets is not None:
            local_dsg_targets = dict()
            for (placement, file_paths) in dsg_targets.iteritems():
                local_file_paths = list()
                for file_path in file_paths:
                    local_file_path = os.path.basename(file_path)
                    local_file_paths.append(local_file_path)
                local_dsg_targets[placement] = local_file_paths
            self._println("dsg_targets = {}".format(local_dsg_targets))
        else:
            self._println("dsg_targets = None")

        self._println("verify = {}".format(verify))
        self._println("database_file_path = {}".format(database_file_path))
        self._println("wait_for_read_confirmation = {}"
                      .format(wait_for_read_confirmation))
        self._println("app_folder = \"{}\"".format(binary_directory))
        self._println("processor_to_app_data_base_address = {}"
                      .format(processor_to_app_data_base_address))
        self._println("scamp_connection_data = \"{}\""
                      .format(scamp_connection_data))
        self._println("executable_targets = ExecutableTargets()")
        for executable_target_key in executable_targets.binary_paths():
            core_subsets = executable_targets.\
                retrieve_cores_for_a_executable_target(executable_target_key)
            self._println("executable_targets.add_binary(r\"{}\")"
                          .format(executable_target_key))
            for core_subset in core_subsets:
                for processor_id in core_subset.processor_ids:
                    self._println(
                        "executable_targets.add_processor(r\"{}\", {}, {}, {})"
                        .format(executable_target_key, core_subset.x,
                                core_subset.y, processor_id))
        self._println("xml_paths = list()")

    def _println(self, line):
        """ Write a line to the script

        :param line: The line to write
        :type line: str
        """
        self._file.write(line)
        self._file.write("\n")

    def add_socket_address(self, socket_address):
        """ Store a socket address for database usage

        :param socket_address: the socket addresses to be stored by the reload
        :return:
        """
        self._println(
            "socket_addresses.append(SocketAddress(\"{}\", {}, {}))"
            .format(socket_address.notify_host_name,
                    socket_address.notify_port_no,
                    socket_address.listen_port))

    def add_routing_table(self, routing_table):
        """ Add a routing table to be reloaded

        :param routing_table: the routing table to reload
        :return:
        """
        reload_routing_table = ReloadRoutingTable()
        location = \
            reload_routing_table.store(self._binary_directory, routing_table)

        self._println("reload_routing_table = ReloadRoutingTable()")
        self._println(
            "routing_tables.add_routing_table(reload_routing_table."
            "reload(\"{}\"))".format(location))

    def add_ip_tag(self, iptag):
        """ Add an iptag to be reloaded

        :param iptag: the iptag object to be loaded.
        :return:
        """
        self._println("iptags.append(")
        self._println("    IPTag(\"{}\", {}, \"{}\", {}, {})) ".format(
            iptag.board_address, iptag.tag, iptag.ip_address, iptag.port,
            iptag.strip_sdp))

    def add_reverse_ip_tag(self, reverse_ip_tag):
        """ Add a reverse ip tag to be reloaded

        :param reverse_ip_tag: the reverse iptag to be loaded.
        :return:
        """
        self._println(
            "reverse_iptags.append(ReverseIPTag(\"{}\", {}, {}, {}, {}, {})) "
            .format(reverse_ip_tag.board_address, reverse_ip_tag.tag,
                    reverse_ip_tag.port, reverse_ip_tag.destination_x,
                    reverse_ip_tag.destination_y, reverse_ip_tag.destination_p,
                    reverse_ip_tag.sdp_port))

    def add_buffered_vertex(self, vertex, iptag, placement, buffered_files):
        """ Add a buffered vertex to be reloaded

        :param vertex: the buffered vertex to be used in reload purposes
        :param iptag: the iptag being used by this vertex
        :param placement: the placement object for this vertex
        :param buffered_files: a list of file paths by region for this vertex
        :return: A dictionary of region -> filename for the vertex
        """
        buffer_tuple = "["
        first = True
        for region in vertex.get_regions():
            if not first:
                buffer_tuple += ", "
            buffer_filename = os.path.basename(buffered_files[region])
            buffer_tuple += "({}, \"{}\", {}) "\
                .format(region, buffer_filename,
                        vertex.get_max_buffer_size_possible(region))
            first = False
        buffer_tuple += "]"
        self._println(
            "vertex = ReloadBufferedVertex(\"{}\", {})".format(
                vertex.label, buffer_tuple))
        self._println(
            "buffered_placements.add_placement("
            "Placement(vertex, {}, {}, {}))".format(
                placement.x, placement.y, placement.p))
        self._println(
            "buffered_tags.add_ip_tag(IPTag(\"{}\", {}, \"{}\", {}, {}), "
            "vertex) ".format(
                iptag.board_address, iptag.tag, iptag.ip_address,
                iptag.port, iptag.strip_sdp))

    def close(self):
        """ Finish writing the reload script
        """
        self._println("")
        self._println(
            "reloader = Reload(machine_name, machine_version, reports_states, "
            "bmp_details, down_chips, down_cores, number_of_boards, height, "
            "width, auto_detect_bmp, enable_reinjection, xml_paths, "
            "scamp_connection_data,boot_port_num, verify, routing_tables,"
            " executable_targets, buffered_tags, iptags, reverse_iptags, "
            "buffered_placements, app_folder, wait_for_read_confirmation, "
            "socket_addresses, database_file_path, runtime, time_scale_factor,"
            "send_start_notification, reset_machine_on_start_up, "
            "processor_to_app_data_base_address, placement_to_app_data_files,"
            "dsg_targets)")
        self._file.close()
