# pacman imports
from pacman.model.placements.placements import Placements
from pacman.model.placements.placement import Placement
from pacman.model.routing_tables import MulticastRoutingTables
from pacman.model.tags import Tags

# spinnmachine imports
from spinn_machine.tags.iptag import IPTag
from spinn_machine.tags.reverse_iptag import ReverseIPTag

# front end common imports
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities.reload.reload_routing_table import \
    ReloadRoutingTable
from spinn_front_end_common.utilities.reload.reload_buffered_vertex \
    import ReloadBufferedVertex
from spinn_front_end_common.utilities.notification_protocol.socket_address \
    import SocketAddress
from spinn_front_end_common.utilities.reload.reload import Reload

# spinnman imports
from spinnman.model.executable_targets \
    import ExecutableTargets

# general imports
import os
import shutil


class ReloadScript(object):
    """ Generates a script for reloading a simulation
    """

    def __init__(
            self,

            # Machine information
            machine_name, version, bmp_details, down_chips, down_cores,
            auto_detect_bmp, enable_reinjection, scamp_connection_data,
            boot_port_num, reset_machine_on_start_up, max_sdram_per_chip,

            # Load data information
            app_data_runtime_folder, exec_dse_on_host, dse_app_id,

            # Database notification information
            wait_for_read_confirmation, database_file_path,
            send_start_notification,

            # Execute information
            app_id, runtime, time_scale_factor, total_machine_timesteps,
            time_threshold):

        self._app_data_runtime_folder = app_data_runtime_folder
        file_name = os.path.join(
            self._app_data_runtime_folder, "rerun_script.py")
        try:
            self._file = open(file_name, "a")
        except IOError:
            raise exceptions.SpinnFrontEndException(
                "Cannot open {} to write the rerun script".format(file_name))

        # Write imports
        self._write_import_class(ExecutableTargets)
        self._write_import_class(MulticastRoutingTables)
        self._write_import_class(Placements)
        self._write_import_class(Placement)
        self._write_import_class(Tags)
        self._write_import_class(IPTag)
        self._write_import_class(ReverseIPTag)
        self._write_import_class(ReloadRoutingTable)
        self._write_import_class(ReloadBufferedVertex)
        self._write_import_class(SocketAddress)
        self._write_import_class(Reload)
        self._println("import os")
        self._println("import logging")
        self._println("import sys")
        self._println("")

        # Write running and loading flags
        self._println("running = False")
        self._println("loading = False")
        self._println("for i in range(1, len(sys.argv)):")
        self._println("    if sys.argv[i] == \"--run\":")
        self._println("        running = True")
        self._println("    if sys.argv[i] == \"--load\":")
        self._println("        loading = True")
        self._println("if not running and not loading:")
        self._println("    running = True")
        self._println("    loading = True")
        self._println("")

        # Write logging system
        self._println("logging.basicConfig(level=logging.INFO)")
        self._println("logger = logging.getLogger(__name__)")
        self._println("for handler in logging.root.handlers:")
        self._println("    handler.setFormatter(logging.Formatter(")
        self._println(
            "        fmt=\"%(asctime)-15s %(levelname)s: %(message)s\",")
        self._println(
            "        datefmt=\"%Y-%m-%d %H:%M:%S\"))")
        self._println("")

        # Write machine inputs
        self._println("machine_name = \"{}\"".format(machine_name))
        self._println("version = {}".format(version))
        self._println("bmp_details = \"{}\"".format(bmp_details))
        self._println("down_chips = \"{}\"".format(down_chips))
        self._println("down_cores = \"{}\"".format(down_cores))
        self._println("auto_detect_bmp = {}".format(auto_detect_bmp))
        self._println("enable_reinjection = {}".format(enable_reinjection))
        self._println("scamp_connection_data = \"{}\"".format(
            scamp_connection_data))
        self._println("boot_port_num = {}".format(boot_port_num))
        self._println("reset_machine_on_start_up = {}".format(
            reset_machine_on_start_up))
        self._println("max_sdram_per_chip = {}".format(max_sdram_per_chip))
        self._println("")

        # Write load data inputs - to be filled in with function calls
        self._println("router_tables = MulticastRoutingTables()")
        self._println("iptags = list()")
        self._println("reverse_iptags = list()")
        self._println(
            "app_data_runtime_folder = os.path.abspath(")
        self._println(
            "    os.path.join(os.path.realpath(\"__file__\"), os.pardir))")
        self._println("dsg_targets = dict()")
        self._println("exec_dse_on_host = {}".format(exec_dse_on_host))
        self._println("dse_app_id = {}".format(dse_app_id))
        self._println("")

        # Write buffered data - to be filled in with function calls
        self._println("buffered_tags = Tags()")
        self._println("buffered_placements = Placements()")
        self._println("")

        # Write database notification data
        self._println("wait_for_read_confirmation = {}".format(
            wait_for_read_confirmation))
        self._println("database_socket_addresses = list()")
        self._println("database_file_path = r\"{}\"".format(
            database_file_path))
        self._println("send_start_notification = {}".format(
            send_start_notification))
        self._println("")

        # Write run data
        self._println("executable_targets = ExecutableTargets()")
        self._println("app_id = {}".format(app_id))
        self._println("runtime = {}".format(runtime))
        self._println("time_scale_factor = {}".format(time_scale_factor))
        self._println("total_machine_timesteps = {}".format(
            total_machine_timesteps))
        self._println("time_threshold = {}".format(time_threshold))
        self._println("")

    def _write_import_class(self, cls):
        self._println("from {} \\".format(cls.__module__))
        self._println("    import {}".format(cls.__name__))

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
        :rtype: None
        """
        self._println("database_socket_addresses.append(")
        self._println("    SocketAddress(\"{}\", {}, {}))".format(
            socket_address.notify_host_name, socket_address.notify_port_no,
            socket_address.listen_port))

    def add_routing_table(self, routing_table):
        """ Add a routing table to be reloaded

        :param routing_table: the routing table to reload
        :rtype: None
        """
        location = ReloadRoutingTable.store(
            self._app_data_runtime_folder, routing_table)

        self._println("router_tables.add_routing_table(")
        self._println("    ReloadRoutingTable.reload(\"{}\"))".format(
            location))

    def add_ip_tag(self, iptag):
        """ Add an iptag to be reloaded

        :param iptag: the iptag object to be loaded.
        :rtype: None
        """
        board_address = None
        if iptag.board_address == "127.0.0.1":
            board_address = "machine_name"
        else:
            board_address = "\"{}\"".format(iptag.board_address)
        self._println("iptags.append(")
        self._println("    IPTag(\"{}\", {}, {}, {}, \"{}\", {}, {})) ".format(
            board_address, iptag.destination_x, iptag.destination_y, iptag.tag,
            iptag.ip_address, iptag.port, iptag.strip_sdp))

    def add_reverse_ip_tag(self, reverse_ip_tag):
        """ Add a reverse ip tag to be reloaded

        :param reverse_ip_tag: the reverse iptag to be loaded.
        :rtype: None
        """
        board_address = None
        if reverse_ip_tag.board_address == "127.0.0.1":
            board_address = "machine_name"
        else:
            board_address = "\"{}\"".format(reverse_ip_tag.board_address)
        self._println("reverse_iptags.append(")
        self._println("    ReverseIPTag(\"{}\", {}, {}, {}, {}, {}))".format(
            board_address, reverse_ip_tag.tag,
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
            buffer_tuple += "({}, \"{}\", {}) ".format(
                region, buffer_filename,
                vertex.get_max_buffer_size_possible(region))
            first = False
        buffer_tuple += "]"
        self._println("vertex = ReloadBufferedVertex(\"{}\", {})".format(
            vertex.label, buffer_tuple))
        self._println("buffered_placements.add_placement(")
        self._println("    Placement(vertex, {}, {}, {}))".format(
            placement.x, placement.y, placement.p))
        self._println("buffered_tags.add_ip_tag(")
        self._println(
            "    IPTag(\"{}\", {}, {}, {}, \"{}\", {}, {}), vertex)".format(
                iptag.board_address, iptag.destination_x, iptag.destination_y,
                iptag.tag, iptag.ip_address, iptag.port, iptag.strip_sdp))

    def add_dsg_target(self, x, y, p, file_path):
        """ Add a Data Specification Generated file to be reloaded

        :param x: The x-coordinate of the chip of the target
        :param y: The y-coordinate of the chip of the target
        :param p: The processor id of the target
        :param file_path: The path of the DSG program to execute
        """
        local_file_path = os.path.basename(file_path)
        self._println("dsg_targets[{}, {}, {}] = \\".format(x, y, p))
        self._println("    r\"{}\"".format(local_file_path))

    def add_executable_target(self, binary, core_subsets):
        """ Add an executable target to be reloaded

        :param binary: The binary to be reloaded
        :param core_subsets: The cores on which to load the binary
        """
        binary_filename = os.path.basename(binary)
        local_file_path = os.path.join(
            self._app_data_runtime_folder, binary_filename)
        shutil.copy(binary, local_file_path)
        for core_subset in core_subsets:
            for processor_id in core_subset.processor_ids:
                self._println("executable_targets.add_processor(")
                self._println("    r\"{}\", {}, {}, {})".format(
                    binary_filename, core_subset.x, core_subset.y,
                    processor_id))

    def close(self):
        """ Finish writing the reload script
        """
        self._println("")
        self._println("reloader = Reload(")
        self._println("    machine_name, version, bmp_details, down_chips,")
        self._println("    down_cores, auto_detect_bmp, enable_reinjection,")
        self._println("    scamp_connection_data, boot_port_num,")
        self._println("    reset_machine_on_start_up, max_sdram_per_chip,")
        self._println("    router_tables, iptags, reverse_iptags,")
        self._println("    app_data_runtime_folder, dsg_targets,")
        self._println("    exec_dse_on_host, dse_app_id,")
        self._println("    buffered_tags, buffered_placements,")
        self._println("    wait_for_read_confirmation,")
        self._println("    database_socket_addresses, database_file_path,")
        self._println("    send_start_notification,")
        self._println("    executable_targets, app_id, runtime,")
        self._println("    time_scale_factor, total_machine_timesteps,")
        self._println("    time_threshold,")
        self._println("    running, loading)")
        self._file.close()
