"""
ReloadScript
"""

# front end common imports
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities import reload
from spinn_front_end_common.utilities.reload.reload_routing_table import \
    ReloadRoutingTable

# general imports
import os
import shutil
import re


class ReloadScript(object):
    """ Generates a script for reloading a simulation
    """

    def __init__(self, binary_directory, hostname, board_version,
                 bmp_details, down_chips, down_cores, number_of_boards,
                 height, width, auto_detect_bmp, enable_reinjection):
        self._binary_directory = binary_directory
        self._wait_on_confiramtion = None
        self._runtime = None
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

    @property
    def wait_on_confirmation(self):
        """
        property method for wait on confirmation
        :return:
        """
        return self._wait_on_confiramtion

    @wait_on_confirmation.setter
    def wait_on_confirmation(self, wait_on_confirmation):
        """
        sets the write on confirmation value for ackhnoeldge protocol
        :param wait_on_confirmation:
        :return:
        """
        self._wait_on_confiramtion = wait_on_confirmation

    @property
    def runtime(self):
        """
        property for runtime
        :return:
        """
        return self._runtime

    @property
    def time_scale_factor(self):
        """
        property for time scale factor
        :return:
        """
        return self._time_scale_factor

    @runtime.setter
    def runtime(self, new_value):
        """
        sets the runtime for the reload script
        :param new_value: new value for runtime
        :return:
        """
        self._runtime = new_value

    @time_scale_factor.setter
    def time_scale_factor(self, new_value):
        """
        sets the timescale factor for the relaod script
        :param new_value: the new value for timescalefactor
        :return:
        """
        self._time_scale_factor = new_value

    def _println(self, line):
        """ Write a line to the script

        :param line: The line to write
        :type line: str
        """
        self._file.write(line)
        self._file.write("\n")

    def add_socket_address(self, socket_address):
        """
        stores a socket address for database usages
        :param socket_address: the socket addresses to be stored by the reload
        :return:
        """
        self._println(
            "socket_addresses.append(SocketAddress(\"{}\", {}, {}))"
            .format(socket_address.notify_host_name,
                    socket_address.notify_port_no,
                    socket_address.listen_port))

    def add_application_data(self, application_data_file_name, placement,
                             base_address):
        """
        stores a placer for an applciation data block
        :param application_data_file_name: the file name where the
        application data is stored.
        :param placement: the core location of the machine where this data
        needs to be stored
        :param base_address: the address in SDRAM where this data should be
         stored.
        :return:
        """
        relative_file_name = application_data_file_name.replace(
            self._binary_directory, "").replace("\\", "\\\\")
        self._println("application_data.append(ReloadApplicationData(")
        self._println("    \"{}\",".format(relative_file_name))
        self._println("    {}, {}, {}, {}))".format(placement.x, placement.y,
                                                    placement.p, base_address))

    def add_routing_table(self, routing_table):
        """
        stores a routertable object for reloading pruposes
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

    def add_binary(self, binary_path, core_subsets):
        """
        stores a binary for reload purposes
        :param binary_path: the absoluete path to the binary needed to be\
                    loaded
        :param core_subsets: the set of cores to which this binary needs to\
                    be loaded on the machine.
        :return:
        """
        create_cs = "CoreSubsets(["
        for core_subset in core_subsets:
            create_cs += "CoreSubset({}, {}, ".format(core_subset.x,
                                                      core_subset.y)
            create_cs += "["
            for processor_id in core_subset.processor_ids:
                create_cs += "{}, ".format(processor_id)
            create_cs += "]),"
        create_cs += "])"
        self._println("binaries.add_subsets(\"{}\", {})".format(
            binary_path.replace("\\", "\\\\"), create_cs))

    def add_ip_tag(self, iptag):
        """
        stores a iptag for loading purposes
        :param iptag: the iptag object to be loaded.
        :return:
        """
        self._println("iptags.append(")
        self._println("    IPTag(\"{}\", {}, \"{}\", {}, {})) ".format(
            iptag.board_address, iptag.tag, iptag.ip_address, iptag.port,
            iptag.strip_sdp))

    def add_reverse_ip_tag(self, reverse_ip_tag):
        """
        stores a reverse iptag for loading purposes
        :param reverse_ip_tag: the reverse iptag to be loaded.
        :return:
        """
        self._println(
            "reverse_iptags.append(ReverseIPTag(\"{}\", {}, {}, {}, {}, {})) "
            .format(reverse_ip_tag.board_address, reverse_ip_tag.tag,
                    reverse_ip_tag.port, reverse_ip_tag.destination_x,
                    reverse_ip_tag.destination_y, reverse_ip_tag.destination_p,
                    reverse_ip_tag.sdp_port))

    def add_buffered_vertex(self, vertex, iptag, placement):
        """
        stores a buffered vertex for loading purposes.
        :param vertex: the buffered vertex to be used in reload purposes
        :param iptag: the iptag being used by this vertex
        :param placement: the placement object for this vertex
        :return: A dictionary of region -> filename for the vertex
        """
        vertex_files = dict()
        buffer_tuple = "["
        first = True
        for region in vertex.get_regions():
            if not first:
                buffer_tuple += ", "
            buffer_filename = "{}_{}".format(
                re.sub("[\"':]", "_", vertex.label), region)
            vertex_files[region] = buffer_filename
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
        return vertex_files

    def close(self):
        """
        cleans up the loading process with whatever is needed to stop
        the applciation
        :return:
        """
        self._println("")
        self._println("reloader = Reload(machine_name, machine_version, "
                      "reports_states, bmp_details, down_chips, down_cores, "
                      "number_of_boards, height, width, auto_detect_bmp,"
                      "enable_reinjection)")
        self._println("if len(socket_addresses) > 0:")
        # note that this needs to be added into the script, as it needs to
        # be able to find its database no matter where it is or where its
        # ran from.
        self._println(
            "    reloader.execute_notification_protocol_read_messages("
            "socket_addresses, {}, os.path.join("
            "os.path.dirname(os.path.abspath(__file__)), "
            "\"input_output_database.db\"))"
            .format(self._wait_on_confiramtion))
        self._println("reloader.reload_application_data(application_data)")
        self._println("reloader.reload_routes(routing_tables)")
        self._println("reloader.reload_tags(iptags, reverse_iptags)")
        self._println("reloader.reload_binaries(binaries)")
        self._println("reloader.enable_buffer_manager(buffered_placements, "
                      "buffered_tags)")
        self._println("reloader.restart(binaries, {}, {}, "
                      "turn_off_machine=True)"
                      .format(self._runtime, self._time_scale_factor))
        self._file.close()
