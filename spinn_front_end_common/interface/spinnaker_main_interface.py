"""
main interface for the spinnaker tools
"""

# pacman imports
from pacman.model.graphs.abstract_virtual_vertex import AbstractVirtualVertex
from pacman.model.graphs.application.impl.application_graph \
    import ApplicationGraph
from pacman.model.graphs.machine.impl.machine_graph import MachineGraph
from pacman.executor.pacman_algorithm_executor import PACMANAlgorithmExecutor
from pacman.exceptions import PacmanAlgorithmFailedToCompleteException

# common front end imports
from spinn_front_end_common.utilities import exceptions as common_exceptions
from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.interface.buffer_management\
    .buffer_models.abstract_receive_buffers_to_host \
    import AbstractReceiveBuffersToHost
from spinn_front_end_common.abstract_models.abstract_recordable \
    import AbstractRecordable
from spinn_front_end_common.abstract_models.abstract_changable_after_run \
    import AbstractChangableAfterRun
from spinn_front_end_common.interface.provenance.pacman_provenance_extractor \
    import PacmanProvenanceExtractor
from spinn_front_end_common.abstract_models\
    .abstract_binary_uses_simulation_run import AbstractBinaryUsesSimulationRun

# general imports
from collections import defaultdict
import logging
import math
import os
import sys
import traceback
import signal

logger = logging.getLogger(__name__)


class SpinnakerMainInterface(object):
    """ Main interface into the tools logic flow
    """

    __slots__ = [
        #
        "_config",

        #
        "_executable_finder",

        #
        "_n_chips_required",

        #
        "_hostname",

        #
        "_spalloc_server",

        #
        "_remote_spinnaker_url",

        #
        "_machine_allocation_controller",

        #
        "_graph_label",

        #
        "_application_graph",

        #
        "_machine_graph",

        #
        "_graph_mapper",

        #
        "_placements",

        #
        "_router_tables",

        #
        "_routing_infos",

        #
        "_tags",

        #
        "_machine",

        #
        "_txrx",

        #
        "_buffer_manager",

        #
        "_ip_address",

        #
        "_machine_outputs",

        #
        "_mapping_outputs",

        #
        "_load_outputs",

        #
        "_last_run_outputs",

        #
        "_pacman_provenance",

        #
        "_xml_paths",

        #
        "_extra_mapping_algorithms",

        #
        "_extra_mapping_inputs",

        #
        "_extra_pre_run_algorithms",

        #
        "_extra_post_run_algorithms",

        #
        "_extra_load_algorithms",

        #
        "_dsg_algorithm",

        #
        "_none_labelled_vertex_count",

        #
        "_none_labelled_edge_count",

        #
        "_database_socket_addresses",

        #
        "_database_interface",

        #
        "_create_database",

        #
        "_database_file_path",

        #
        "_has_ran",

        #
        "_has_reset_last",

        #
        "_current_run_timesteps",

        #
        "_no_sync_changes",

        #
        "_minimum_step_generated",

        #
        "_no_machine_time_steps",

        #
        "_machine_time_step",

        #
        "_time_scale_factor",

        #
        "_app_id",

        #
        "_report_default_directory",

        #
        "_app_data_runtime_folder",

        #
        "_json_folder",

        #
        "_provenance_file_path",

        #
        "_do_timings",

        #
        "_print_timings",

        #
        "_provenance_format",

        #
        "_exec_dse_on_host",

        #
        "_use_virtual_board",

        #
        "_raise_keyboard_interrupt"
    ]

    def __init__(
            self, config, executable_finder, graph_label=None,
            database_socket_addresses=None, extra_algorithm_xml_paths=None,
            extra_mapping_inputs=None, extra_mapping_algorithms=None,
            extra_pre_run_algorithms=None, extra_post_run_algorithms=None,
            n_chips_required=None, extra_load_algorithms=None):

        # global params
        self._config = config

        self._executable_finder = executable_finder

        # output locations of binaries to be searched for end user info
        logger.info(
            "Will search these locations for binaries: {}"
            .format(self._executable_finder.binary_paths))

        self._n_chips_required = n_chips_required
        self._hostname = None
        self._spalloc_server = None
        self._remote_spinnaker_url = None
        self._machine_allocation_controller = None

        # update graph label if needed
        if graph_label is None:
            self._graph_label = "Application_graph"
        else:
            self._graph_label = graph_label

        # pacman objects
        self._application_graph = ApplicationGraph(label=self._graph_label)
        self._machine_graph = MachineGraph(label=self._graph_label)
        self._graph_mapper = None
        self._placements = None
        self._router_tables = None
        self._routing_infos = None
        self._tags = None
        self._machine = None
        self._txrx = None
        self._buffer_manager = None
        self._ip_address = None

        # pacman executor objects
        self._machine_outputs = None
        self._mapping_outputs = None
        self._load_outputs = None
        self._last_run_outputs = None
        self._pacman_provenance = PacmanProvenanceExtractor()
        self._xml_paths = self._create_xml_paths(extra_algorithm_xml_paths)

        # extra algorithms and inputs for runs, should disappear in future
        #  releases
        self._extra_mapping_algorithms = list()
        if extra_mapping_algorithms is not None:
            self._extra_mapping_algorithms.extend(extra_mapping_algorithms)
        self._extra_mapping_inputs = dict()
        if extra_mapping_inputs is not None:
            self._extra_mapping_inputs.update(extra_mapping_inputs)
        self._extra_pre_run_algorithms = list()
        if extra_pre_run_algorithms is not None:
            self._extra_pre_run_algorithms = \
                extra_pre_run_algorithms + self._extra_pre_run_algorithms
        self._extra_post_run_algorithms = list()
        if extra_post_run_algorithms is not None:
            self._extra_post_run_algorithms.extend(extra_post_run_algorithms)
        self._extra_load_algorithms = list()
        if extra_load_algorithms is not None:
            self._extra_load_algorithms.extend(extra_load_algorithms)

        self._dsg_algorithm = \
            "FrontEndCommonApplicationGraphDataSpecificationWriter"

        # vertex label safety (used by reports mainly)
        self._none_labelled_vertex_count = 0
        self._none_labelled_edge_count = 0

        # database objects
        self._database_socket_addresses = set()
        if database_socket_addresses is not None:
            self._database_socket_addresses.update(database_socket_addresses)
        self._database_interface = None
        self._create_database = None
        self._database_file_path = None

        # holder for timing related values
        self._has_ran = False
        self._has_reset_last = False
        self._current_run_timesteps = 0
        self._no_sync_changes = 0
        self._minimum_step_generated = None
        self._no_machine_time_steps = None
        self._machine_time_step = None
        self._time_scale_factor = None

        self._app_id = self._config.getint("Machine", "appID")

        # set up reports default folder
        self._report_default_directory, this_run_time_string = \
            helpful_functions.set_up_report_specifics(
                default_report_file_path=self._config.get(
                    "Reports", "defaultReportFilePath"),
                max_reports_kept=self._config.getint(
                    "Reports", "max_reports_kept"),
                app_id=self._app_id)

        # set up application report folder
        self._app_data_runtime_folder = \
            helpful_functions.set_up_output_application_data_specifics(
                max_application_binaries_kept=self._config.getint(
                    "Reports", "max_application_binaries_kept"),
                where_to_write_application_data_files=self._config.get(
                    "Reports", "defaultApplicationDataFilePath"),
                app_id=self._app_id,
                this_run_time_string=this_run_time_string)

        self._json_folder = os.path.join(
            self._report_default_directory, "json_files")
        if not os.path.exists(self._json_folder):
            os.makedirs(self._json_folder)

        # make a folder for the provenance data storage
        self._provenance_file_path = os.path.join(
            self._report_default_directory, "provenance_data")
        if not os.path.exists(self._provenance_file_path):
            os.makedirs(self._provenance_file_path)

        # timing provenance elements
        self._do_timings = self._config.getboolean(
            "Reports", "writeAlgorithmTimings")
        self._print_timings = self._config.getboolean(
            "Reports", "display_algorithm_timings")
        self._provenance_format = self._config.get(
            "Reports", "provenance_format")
        if self._provenance_format not in ["xml", "json"]:
            raise Exception("Unknown provenance format: {}".format(
                self._provenance_format))
        self._exec_dse_on_host = self._config.getboolean(
            "SpecExecution", "specExecOnHost")

        # set up machine targeted data
        self._use_virtual_board = self._config.getboolean(
            "Machine", "virtual_board")

        # log app id to end user
        logger.info("Setting appID to %d." % self._app_id)

        # Setup for signal handling
        self._raise_keyboard_interrupt = False

    def set_up_machine_specifics(self, hostname):
        """ Adds machine specifics for the different modes of execution

        :param hostname:
        :return:
        """
        if hostname is not None:
            self._hostname = hostname
            logger.warn("The machine name from setup call is overriding the "
                        "machine name defined in the config file")
        else:
            self._hostname = self._read_config("Machine", "machineName")
            self._spalloc_server = self._read_config(
                "Machine", "spalloc_server")
            self._remote_spinnaker_url = self._read_config(
                "Machine", "remote_spinnaker_url")
        if (self._hostname is None and self._spalloc_server is None and
                self._remote_spinnaker_url is None and
                not self._use_virtual_board):
            raise Exception(
                "A SpiNNaker machine must be specified your configuration"
                " file")

        n_items_specified = sum([
            1 if item is not None else 0
            for item in [
                self._hostname, self._spalloc_server,
                self._remote_spinnaker_url]])

        if (n_items_specified > 1 or
                (n_items_specified == 1 and self._use_virtual_board)):
            raise Exception(
                "Only one of machineName, spalloc_server, "
                "remote_spinnaker_url and virtual_board should be specified "
                "in your configuration files")

        if self._spalloc_server is not None:
            if self._read_config("Machine", "spalloc_user") is None:
                raise Exception(
                    "A spalloc_user must be specified with a spalloc_server")

    def signal_handler(self, signal, frame):

        # If we are to raise the keyboard interrupt, do so
        if self._raise_keyboard_interrupt:
            raise KeyboardInterrupt

        logger.error("User has cancelled simulation")
        self._shutdown()

    def exception_handler(self, exctype, value, traceback_obj):
        self._shutdown()
        return sys.__excepthook__(exctype, value, traceback_obj)

    def run(self, run_time):
        """

        :param run_time: the run duration in milliseconds.
        :return: None
        """
        # Install the Control-C handler
        signal.signal(signal.SIGINT, self.signal_handler)
        self._raise_keyboard_interrupt = True
        sys.excepthook = sys.__excepthook__

        logger.info("Starting execution process")

        n_machine_time_steps = None
        total_run_time = None
        if run_time is not None:
            n_machine_time_steps = int(
                (run_time * 1000.0) / self._machine_time_step)
            total_run_timesteps = (
                self._current_run_timesteps + n_machine_time_steps)
            total_run_time = (
                total_run_timesteps *
                (float(self._machine_time_step) / 1000.0) *
                self._time_scale_factor)
        if self._machine_allocation_controller is not None:
            self._machine_allocation_controller.extend_allocation(
                total_run_time)

        # If we have never run before, or the graph has changed,
        # start by performing mapping
        application_graph_changed = self._detect_if_graph_has_changed(True)
        if not self._has_ran or application_graph_changed:
            if (application_graph_changed and self._has_ran and
                    not self._has_reset_last):
                self.stop()
                raise NotImplementedError(
                    "The network cannot be changed between runs without"
                    " resetting")

            # Reset the machine graph if there is an application graph
            if len(self._application_graph.vertices) > 0:
                self._machine_graph = MachineGraph(self._graph_label)
                self._graph_mapper = None

            # Reset the machine if the machine is a spalloc machine and the
            # graph has changed
            if (application_graph_changed and self._hostname is None and
                    not self._use_virtual_board):
                self._machine = None

            if self._machine is None:
                self._get_machine(total_run_time, n_machine_time_steps)
            self._do_mapping(run_time, n_machine_time_steps, total_run_time)

        # Check if anything is recording and buffered
        is_buffered_recording = False
        for placement in self._placements.placements:
            vertex = placement.vertex
            if (isinstance(vertex, AbstractReceiveBuffersToHost) and
                    isinstance(vertex, AbstractRecordable)):
                if vertex.is_recording():
                    is_buffered_recording = True
                    break

        # Check if everything can update the run time
        is_runtime_updatable = True
        for placement in self._placements.placements:
            if not isinstance(
                    placement.vertex, AbstractBinaryUsesSimulationRun):
                if self._graph_mapper is None:
                    is_runtime_updatable = False
                    break
                else:
                    app_vertex = self._graph_mapper.get_application_vertex(
                        placement.vertex)
                    if not isinstance(
                            app_vertex, AbstractBinaryUsesSimulationRun):
                        is_runtime_updatable = False
        if not is_runtime_updatable:
            self._config.set("Buffers", "use_auto_pause_and_resume", "False")

        # Work out an array of timesteps to perform
        if (not self._config.getboolean(
                "Buffers", "use_auto_pause_and_resume") or
                not is_buffered_recording):

            # Not currently possible to run the second time for more than the
            # first time without auto pause and resume
            if (is_buffered_recording and
                    self._minimum_step_generated is not None and
                    (self._minimum_step_generated < n_machine_time_steps or
                        n_machine_time_steps is None)):
                raise common_exceptions.ConfigurationException(
                    "Second and subsequent run time must be less than or equal"
                    " to the first run time")

            steps = [n_machine_time_steps]
            self._minimum_step_generated = steps[0]
        else:

            if run_time is None:
                raise Exception(
                    "Cannot use automatic pause and resume with an infinite "
                    "run time")

            # With auto pause and resume, any time step is possible but run
            # time more than the first will guarantee that run will be called
            # more than once
            if self._minimum_step_generated is not None:
                steps = self._generate_steps(
                    n_machine_time_steps, self._minimum_step_generated)
            else:
                steps = self._deduce_number_of_iterations(n_machine_time_steps)
                self._minimum_step_generated = steps[0]

        # If we have never run before, or the graph has changed, or a reset
        # has been requested, load the data
        if (not self._has_ran or application_graph_changed or
                self._has_reset_last):

            # Data generation needs to be done if not already done
            if not self._has_ran or application_graph_changed:
                self._do_data_generation(steps[0])

            # If we are using a virtual board, don't load
            if not self._use_virtual_board:
                self._do_load()

        # Run for each of the given steps
        logger.info("Running for {} steps for a total of {} ms".format(
            len(steps), run_time))
        for i, step in enumerate(steps):
            logger.info("Run {} of {}".format(i + 1, len(steps)))
            self._do_run(step)

        # Indicate that the signal handler needs to act
        self._raise_keyboard_interrupt = False
        sys.excepthook = self.exception_handler

    def _deduce_number_of_iterations(self, n_machine_time_steps):

        # Go through the placements and find how much SDRAM is available
        # on each chip
        sdram_tracker = dict()
        vertex_by_chip = defaultdict(list)
        for placement in self._placements.placements:
            vertex = placement.vertex
            if isinstance(vertex, AbstractReceiveBuffersToHost):
                resources = vertex.resources_required
                if (placement.x, placement.y) not in sdram_tracker:
                    sdram_tracker[placement.x, placement.y] = \
                        self._machine.get_chip_at(
                            placement.x, placement.y).sdram.size
                sdram = (
                    resources.sdram.get_value() -
                    vertex.get_minimum_buffer_sdram_usage())
                sdram_tracker[placement.x, placement.y] -= sdram
                vertex_by_chip[placement.x, placement.y].append(vertex)

        # Go through the chips and divide up the remaining SDRAM, finding
        # the minimum number of machine timesteps to assign
        min_time_steps = None
        for x, y in vertex_by_chip:
            vertices_on_chip = vertex_by_chip[x, y]
            sdram = sdram_tracker[x, y]
            sdram_per_vertex = int(sdram / len(vertices_on_chip))
            for vertex in vertices_on_chip:
                n_time_steps = vertex.get_n_timesteps_in_buffer_space(
                    sdram_per_vertex)
                if min_time_steps is None or n_time_steps < min_time_steps:
                    min_time_steps = n_time_steps
        if min_time_steps is None:
            return [n_machine_time_steps]
        else:
            return self._generate_steps(n_machine_time_steps, min_time_steps)

    @staticmethod
    def _generate_steps(n_machine_time_steps, min_machine_time_steps):
        number_of_full_iterations = int(math.floor(
            n_machine_time_steps / min_machine_time_steps))
        left_over_time_steps = int(
            n_machine_time_steps -
            (number_of_full_iterations * min_machine_time_steps))

        steps = [int(min_machine_time_steps)] * number_of_full_iterations
        if left_over_time_steps != 0:
            steps.append(int(left_over_time_steps))
        return steps

    def _calculate_number_of_machine_time_steps(self, next_run_timesteps):
        total_run_timesteps = next_run_timesteps
        if next_run_timesteps is not None:
            total_run_timesteps += self._current_run_timesteps
            machine_time_steps = (
                (total_run_timesteps * 1000.0) / self._machine_time_step)
            if machine_time_steps != int(machine_time_steps):
                logger.warn(
                    "The runtime and machine time step combination result in "
                    "a fractional number of machine time steps")
            self._no_machine_time_steps = int(math.ceil(machine_time_steps))
        else:
            self._no_machine_time_steps = None
            for vertex in self._application_graph.vertices:
                if (isinstance(vertex, AbstractRecordable) and
                        vertex.is_recording()):
                    raise common_exceptions.ConfigurationException(
                        "recording a vertex when set to infinite runtime "
                        "is not currently supported")
            for vertex in self._machine_graph.vertices:
                if (isinstance(vertex, AbstractRecordable) and
                        vertex.is_recording()):
                    raise common_exceptions.ConfigurationException(
                        "recording a vertex when set to infinite runtime "
                        "is not currently supported")
        return total_run_timesteps

    def _run_machine_algorithms(
            self, inputs, algorithms, outputs, optional_algorithms=None):

        optional = optional_algorithms
        if optional is None:
            optional = []

        # Execute the algorithms
        executor = PACMANAlgorithmExecutor(
            algorithms=algorithms, optional_algorithms=optional,
            inputs=inputs, xml_paths=self._xml_paths, required_outputs=outputs,
            do_timings=self._do_timings, print_timings=self._print_timings)

        try:
            executor.execute_mapping()
            self._pacman_provenance.extract_provenance(executor)
            return executor
        except:
            self._txrx = executor.get_item("MemoryTransceiver")
            self._machine_allocation_controller = executor.get_item(
                "MachineAllocationController")
            self._shutdown()
            ex_type, ex_value, ex_traceback = sys.exc_info()
            raise ex_type, ex_value, ex_traceback

    def _get_machine(self, total_run_time=0, n_machine_time_steps=None):
        if self._machine is not None:
            return self._machine

        inputs = dict()
        algorithms = list()
        outputs = list()

        # add the application and machine graphs as needed
        if len(self._application_graph.vertices) > 0:
            inputs["MemoryApplicationGraph"] = self._application_graph
        elif len(self._machine_graph.vertices) > 0:
            inputs["MemoryMachineGraph"] = self._machine_graph

        # add reinjection flag
        inputs["EnableReinjectionFlag"] = self._config.getboolean(
            "Machine", "enable_reinjection")

        # add max sdram size which we're going to allow (debug purposes)
        inputs["MaxSDRAMSize"] = self._read_config_int(
            "Machine", "max_sdram_allowed_per_chip")

        # Set the total run time
        inputs["TotalRunTime"] = total_run_time
        inputs["TotalMachineTimeSteps"] = n_machine_time_steps
        inputs["MachineTimeStep"] = self._machine_time_step

        # If we are using a directly connected machine, add the details to get
        # the machine and transceiver
        if self._hostname is not None:
            inputs["IPAddress"] = self._hostname
            inputs["BMPDetails"] = self._read_config("Machine", "bmp_names")
            inputs["DownedChipsDetails"] = self._config.get(
                "Machine", "down_chips")
            inputs["DownedCoresDetails"] = self._config.get(
                "Machine", "down_cores")
            inputs["DownedLinksDetails"] = self._convert_down_links(
                self._config.get("Machine", "down_links"))
            inputs["AutoDetectBMPFlag"] = self._config.getboolean(
                "Machine", "auto_detect_bmp")
            inputs["ScampConnectionData"] = self._read_config(
                "Machine", "scamp_connections_data")
            inputs["BootPortNum"] = self._read_config_int(
                "Machine", "boot_connection_port_num")
            inputs["BoardVersion"] = self._read_config_int(
                "Machine", "version")
            inputs["ResetMachineOnStartupFlag"] = self._config.getboolean(
                "Machine", "reset_machine_on_startup")
            inputs["MaxCoreId"] = self._read_config_int(
                "Machine", "core_limit")

            algorithms.append("FrontEndCommonMachineGenerator")
            algorithms.append("MallocBasedChipIDAllocator")

            outputs.append("MemoryExtendedMachine")
            outputs.append("MemoryTransceiver")

            executor = self._run_machine_algorithms(
                inputs, algorithms, outputs)
            self._machine = executor.get_item("MemoryExtendedMachine")
            self._txrx = executor.get_item("MemoryTransceiver")
            self._machine_outputs = executor.get_items()

        if self._use_virtual_board:
            inputs["IPAddress"] = "virtual"
            inputs["BoardVersion"] = self._read_config_int(
                "Machine", "version")
            inputs["NumberOfBoards"] = self._read_config_int(
                "Machine", "number_of_boards")
            inputs["MachineWidth"] = self._read_config_int(
                "Machine", "width")
            inputs["MachineHeight"] = self._read_config_int(
                "Machine", "height")
            inputs["BMPDetails"] = None
            inputs["DownedChipsDetails"] = self._config.get(
                "Machine", "down_chips")
            inputs["DownedCoresDetails"] = self._config.get(
                "Machine", "down_cores")
            inputs["DownedLinksDetails"] = self._convert_down_links(
                self._config.get("Machine", "down_links"))
            inputs["AutoDetectBMPFlag"] = False
            inputs["ScampConnectionData"] = None
            inputs["BootPortNum"] = self._read_config_int(
                "Machine", "boot_connection_port_num")
            inputs["ResetMachineOnStartupFlag"] = self._config.getboolean(
                "Machine", "reset_machine_on_startup")
            inputs["MemoryTransceiver"] = None
            if self._config.getboolean("Machine", "enable_reinjection"):
                inputs["CPUsPerVirtualChip"] = 15
            else:
                inputs["CPUsPerVirtualChip"] = 16

            algorithms.append("FrontEndCommonVirtualMachineGenerator")
            algorithms.append("MallocBasedChipIDAllocator")

            outputs.append("MemoryExtendedMachine")

            executor = self._run_machine_algorithms(
                inputs, algorithms, outputs)
            self._machine_outputs = executor.get_items()
            self._machine = executor.get_item("MemoryExtendedMachine")

        if (self._spalloc_server is not None or
                self._remote_spinnaker_url is not None):

            need_virtual_board = False

            # if using spalloc system
            if self._spalloc_server is not None:
                inputs["SpallocServer"] = self._spalloc_server
                inputs["SpallocPort"] = self._read_config_int(
                    "Machine", "spalloc_port")
                inputs["SpallocUser"] = self._read_config(
                    "Machine", "spalloc_user")
                inputs["SpallocMachine"] = self._read_config(
                    "Machine", "spalloc_machine")
                if self._n_chips_required is None:
                    algorithms.append(
                        "FrontEndCommonSpallocMaxMachineGenerator")
                    need_virtual_board = True

            # if using HBP server system
            if self._remote_spinnaker_url is not None:
                inputs["RemoteSpinnakerUrl"] = self._remote_spinnaker_url
                if self._n_chips_required is None:
                    algorithms.append("FrontEndCommonHBPMaxMachineGenerator")
                    need_virtual_board = True

            if (len(self._application_graph.vertices) == 0 and
                    len(self._machine_graph.vertices) == 0 and
                    need_virtual_board):
                raise common_exceptions.ConfigurationException(
                    "A allocated machine has been requested but there are no"
                    " vertices to work out the size of the machine required"
                    " and n_chips_required has not been set")

            if self._config.getboolean("Machine", "enable_reinjection"):
                inputs["CPUsPerVirtualChip"] = 15
            else:
                inputs["CPUsPerVirtualChip"] = 16

            do_partitioning = False
            if need_virtual_board:
                algorithms.append("FrontEndCommonVirtualMachineGenerator")
                algorithms.append("MallocBasedChipIDAllocator")

                # If we are using an allocation server, and we need a virtual
                # board, we need to use the virtual board to get the number of
                # chips to be allocated either by partitioning, or by measuring
                # the graph
                if len(self._application_graph.vertices) != 0:
                    inputs["MemoryApplicationGraph"] = \
                        self._application_graph
                    algorithms.extend(self._config.get(
                        "Mapping",
                        "application_to_machine_graph_algorithms").split(","))
                    outputs.append("MemoryMachineGraph")
                    outputs.append("MemoryGraphMapper")
                    do_partitioning = True
                elif len(self._machine_graph.vertices) != 0:
                    inputs["MemoryMachineGraph"] = self._machine_graph
                    algorithms.append("FrontEndCommonGraphMeasurer")
            else:

                # If we are using an allocation server but have been told how
                # many chips to use, just use that as an input
                inputs["NChipsRequired"] = self._n_chips_required

            if self._spalloc_server is not None:
                algorithms.append("FrontEndCommonSpallocAllocator")
            elif self._remote_spinnaker_url is not None:
                algorithms.append("FrontEndCommonHBPAllocator")
            algorithms.append("FrontEndCommonMachineGenerator")
            algorithms.append("MallocBasedChipIDAllocator")

            outputs.append("MemoryExtendedMachine")
            outputs.append("IPAddress")
            outputs.append("MemoryTransceiver")
            outputs.append("MachineAllocationController")

            executor = self._run_machine_algorithms(
                inputs, algorithms, outputs)

            self._machine_outputs = executor.get_items()
            self._machine = executor.get_item("MemoryExtendedMachine")
            self._ip_address = executor.get_item("IPAddress")
            self._txrx = executor.get_item("MemoryTransceiver")
            self._machine_allocation_controller = executor.get_item(
                "MachineAllocationController")

            if do_partitioning:
                self._machine_graph = executor.get_item(
                    "MemoryMachineGraph")
                self._graph_mapper = executor.get_item(
                    "MemoryGraphMapper")

        return self._machine

    def _convert_down_links(self, down_link_text):
        """ Converts the text form to a list of down links

        :param down_link_text: the text from the config system
        :return:\
            array of (tuple(int, int), tuple(int, int), int) where the\
            first tuple is the source x and y for the chip the link is from,\
            the second is a destination x and y for the chip the link goes to,\
            the third is the link id from the source chip.
        """
        down_links = list()
        if down_link_text == "None":
            return down_links

        bits = down_link_text.split("]")
        for bit in bits:
            if len(bit) > 0:
                removed_first_bracket = bit.split("[")
                coords_bits = removed_first_bracket[1].split(":")
                source_bits = coords_bits[0].split(",")
                removed_bracket_sx = source_bits[0].split("(")[1]
                removed_bracket_sy = source_bits[1].split(")")[0]
                source_tuple = (int(removed_bracket_sx),
                                int(removed_bracket_sy))
                dest_bits = coords_bits[1].split(",")
                removed_bracket_dx = dest_bits[0].split("(")[1]
                removed_bracket_dy = dest_bits[1].split(")")[0]
                dest_tuple = (int(removed_bracket_dx), int(removed_bracket_dy))
                link_id = int(coords_bits[2])
                down_links.append((source_tuple, dest_tuple, link_id))
        print bits
        return down_links

    def generate_file_machine(self):
        inputs = {
            "MemoryExtendedMachine": self.machine,
            "FileMachineFilePath": os.path.join(
                self._json_folder, "machine.json")
        }
        outputs = ["FileMachine"]
        executor = PACMANAlgorithmExecutor(
            algorithms=[], optional_algorithms=[], inputs=inputs,
            xml_paths=self._xml_paths, required_outputs=outputs,
            do_timings=self._do_timings, print_timings=self._print_timings)
        executor.execute_mapping()

    def _do_mapping(self, run_time, n_machine_time_steps, total_run_time):

        # update inputs with extra mapping inputs if required
        inputs = dict(self._machine_outputs)
        if self._extra_mapping_inputs is not None:
            inputs.update(self._extra_mapping_inputs)

        inputs["RunTime"] = run_time
        inputs["TotalRunTime"] = total_run_time
        inputs["TotalMachineTimeSteps"] = n_machine_time_steps
        inputs["PostSimulationOverrunBeforeError"] = self._config.getint(
            "Machine", "post_simulation_overrun_before_error")

        # handle graph additions
        if (len(self._application_graph.vertices) > 0 and
                self._graph_mapper is None):
            inputs["MemoryApplicationGraph"] = self._application_graph
        elif len(self._machine_graph.vertices) > 0:
            inputs['MemoryMachineGraph'] = self._machine_graph
            if self._graph_mapper is not None:
                inputs["MemoryGraphMapper"] = self._graph_mapper
        else:
            raise common_exceptions.ConfigurationException(
                "There needs to be a graph which contains at least one vertex"
                " for the tool chain to map anything.")

        inputs['ReportFolder'] = self._report_default_directory
        inputs["ApplicationDataFolder"] = self._app_data_runtime_folder
        inputs["APPID"] = self._app_id
        inputs["DSEAppID"] = self._config.getint("Machine", "DSEAppID")
        inputs["ExecDSEOnHostFlag"] = self._exec_dse_on_host
        inputs["TimeScaleFactor"] = self._time_scale_factor
        inputs["MachineTimeStep"] = self._machine_time_step
        inputs["DatabaseSocketAddresses"] = self._database_socket_addresses
        inputs["DatabaseWaitOnConfirmationFlag"] = self._config.getboolean(
            "Database", "wait_on_confirmation")
        inputs["WriteCheckerFlag"] = self._config.getboolean(
            "Mode", "verify_writes")
        inputs["WriteTextSpecsFlag"] = self._config.getboolean(
            "Reports", "writeTextSpecs")
        inputs["ExecutableFinder"] = self._executable_finder
        inputs["MachineHasWrapAroundsFlag"] = self._read_config_boolean(
            "Machine", "requires_wrap_arounds")
        inputs["UserCreateDatabaseFlag"] = self._config.get(
            "Database", "create_database")
        inputs["SendStartNotifications"] = self._config.getboolean(
            "Database", "send_start_notification")

        # add paths for each file based version
        inputs["FileCoreAllocationsFilePath"] = os.path.join(
            self._json_folder, "core_allocations.json")
        inputs["FileSDRAMAllocationsFilePath"] = os.path.join(
            self._json_folder, "sdram_allocations.json")
        inputs["FileMachineFilePath"] = os.path.join(
            self._json_folder, "machine.json")
        inputs["FileMachineGraphFilePath"] = os.path.join(
            self._json_folder, "machine_graph.json")
        inputs["FilePlacementFilePath"] = os.path.join(
            self._json_folder, "placements.json")
        inputs["FileRoutingPathsFilePath"] = os.path.join(
            self._json_folder, "routing_paths.json")
        inputs["FileConstraintsFilePath"] = os.path.join(
            self._json_folder, "constraints.json")

        # handle extra mapping algorithms if required
        if self._extra_mapping_algorithms is not None:
            algorithms = list(self._extra_mapping_algorithms)
        else:
            algorithms = list()

        # Add reports
        if self._config.getboolean("Reports", "reportsEnabled"):
            if self._config.getboolean("Reports", "writeTagAllocationReports"):
                algorithms.append("TagReport")
            if self._config.getboolean("Reports", "writeRouterInfoReport"):
                algorithms.append("routingInfoReports")
            if self._config.getboolean("Reports", "writeRouterReports"):
                algorithms.append("RouterReports")
            if self._config.getboolean("Reports", "writeRoutingTableReports"):
                algorithms.append("unCompressedRoutingTableReports")
                algorithms.append("compressedRoutingTableReports")
                algorithms.append("comparisonOfRoutingTablesReport")

            # only add partitioner report if using an application graph
            if (self._config.getboolean(
                    "Reports", "writePartitionerReports") and
                    len(self._application_graph.vertices) != 0):
                algorithms.append("PartitionerReport")

            # only add write placer report with application graph when
            # there's application vertices
            if (self._config.getboolean(
                    "Reports", "writeApplicationGraphPlacerReport") and
                    len(self._application_graph.vertices) != 0):
                algorithms.append("PlacerReportWithApplicationGraph")

            if self._config.getboolean(
                    "Reports", "writeMachineGraphPlacerReport"):
                algorithms.append("PlacerReportWithoutApplicationGraph")

            # only add network specification report if there's
            # application vertices.
            if (self._config.getboolean(
                    "Reports", "writeNetworkSpecificationReport") and
                    len(self._application_graph.vertices) != 0):
                algorithms.append(
                    "FrontEndCommonApplicationGraphNetworkSpecificationReport")

        # only add the partitioner if there isn't already a machine graph
        if (len(self._application_graph.vertices) > 0 and
                len(self._machine_graph.vertices) == 0):
            algorithms.extend(self._config.get(
                "Mapping",
                "application_to_machine_graph_algorithms").split(","))

        algorithms.extend(self._config.get(
            "Mapping", "machine_graph_to_machine_algorithms").split(","))

        outputs = [
            "MemoryPlacements", "MemoryRoutingTables",
            "MemoryTags", "MemoryRoutingInfos",
            "MemoryMachineGraph"
        ]

        if len(self._application_graph.vertices) > 0:
            outputs.append("MemoryGraphMapper")

        # Execute the mapping algorithms
        executor = self._run_machine_algorithms(inputs, algorithms, outputs)
        self._mapping_outputs = executor.get_items()
        self._pacman_provenance.extract_provenance(executor)

        # Get the outputs needed
        self._placements = executor.get_item("MemoryPlacements")
        self._router_tables = executor.get_item("MemoryRoutingTables")
        self._tags = executor.get_item("MemoryTags")
        self._routing_infos = executor.get_item("MemoryRoutingInfos")
        self._graph_mapper = executor.get_item("MemoryGraphMapper")
        self._machine_graph = executor.get_item("MemoryMachineGraph")

    def _do_data_generation(self, n_machine_time_steps):

        # The initial inputs are the mapping outputs
        inputs = dict(self._mapping_outputs)
        inputs["FirstMachineTimeStep"] = self._current_run_timesteps

        # Run the data generation algorithms
        algorithms = [self._dsg_algorithm]

        executor = self._run_machine_algorithms(inputs, algorithms, [])
        self._mapping_outputs = executor.get_items()
        self._pacman_provenance.extract_provenance(executor)

    def _do_load(self):

        # The initial inputs are the mapping outputs
        inputs = dict(self._mapping_outputs)
        inputs["WriteMemoryMapReportFlag"] = (
            self._config.getboolean("Reports", "reportsEnabled") and
            self._config.getboolean("Reports", "writeMemoryMapReport")
        )

        algorithms = list(self._extra_load_algorithms)
        optional_algorithms = list()
        optional_algorithms.append("FrontEndCommonRoutingTableLoader")
        optional_algorithms.append("FrontEndCommonTagsLoader")
        if self._exec_dse_on_host:
            optional_algorithms.append(
                "FrontEndCommonHostExecuteDataSpecification")
            if self._config.getboolean("Reports", "writeMemoryMapReport"):
                optional_algorithms.append(
                    "FrontEndCommonMemoryMapOnHostReport")
        else:
            optional_algorithms.append(
                "FrontEndCommonMachineExecuteDataSpecification")  # @IgnorePep8
            if self._config.getboolean("Reports", "writeMemoryMapReport"):
                optional_algorithms.append(
                    "FrontEndCommonMemoryMapOnChipReport")

        # algorithms needed for loading the binaries to the SpiNNaker machine
        optional_algorithms.append("FrontEndCommonGraphBinaryGatherer")
        optional_algorithms.append("FrontEndCommonLoadExecutableImages")

        # expected outputs from this phase
        outputs = [
            "LoadedReverseIPTagsToken", "LoadedIPTagsToken",
            "LoadedRoutingTablesToken", "LoadBinariesToken",
            "LoadedApplicationDataToken"
        ]

        executor = self._run_machine_algorithms(
            inputs, algorithms, outputs, optional_algorithms)
        self._load_outputs = executor.get_items()
        self._pacman_provenance.extract_provenance(executor)

    def _do_run(self, n_machine_time_steps):

        # calculate number of machine time steps
        total_run_timesteps = self._calculate_number_of_machine_time_steps(
            n_machine_time_steps)
        run_time = None
        if n_machine_time_steps is not None:
            run_time = (
                n_machine_time_steps *
                (float(self._machine_time_step) / 1000.0)
            )

        # if running again, load the outputs from last load or last mapping
        if self._load_outputs is not None:
            inputs = dict(self._load_outputs)
        else:
            inputs = dict(self._mapping_outputs)

        inputs["RanToken"] = self._has_ran
        inputs["NoSyncChanges"] = self._no_sync_changes
        inputs["ProvenanceFilePath"] = self._provenance_file_path
        inputs["RunTimeMachineTimeSteps"] = n_machine_time_steps
        inputs["TotalMachineTimeSteps"] = total_run_timesteps
        inputs["RunTime"] = run_time
        inputs["FirstMachineTimeStep"] = self._current_run_timesteps

        # update algorithm list with extra pre algorithms if needed
        if self._extra_pre_run_algorithms is not None:
            algorithms = list(self._extra_pre_run_algorithms)
        else:
            algorithms = list()

        # If we have run before, make sure to extract the data before the next
        # run
        if self._has_ran and not self._has_reset_last:
            algorithms.append("FrontEndCommonBufferExtractor")

        # Create a buffer manager if there isn't one already
        if self._buffer_manager is None:
            inputs["WriteReloadFilesFlag"] = False
            algorithms.append("FrontEndCommonBufferManagerCreator")
        else:
            inputs["BufferManager"] = self._buffer_manager

        if not self._use_virtual_board:
            algorithms.append("FrontEndCommonChipRuntimeUpdater")

        # Add the database writer in case it is needed
        algorithms.append("FrontEndCommonDatabaseInterface")
        if not self._use_virtual_board:
            algorithms.append("FrontEndCommonNotificationProtocol")

        # Sort out reload if needed
        if self._config.getboolean("Reports", "writeReloadSteps"):
            logger.warn("Reload script is not supported in this version")

        outputs = [
            "NoSyncChanges",
            "BufferManager"
        ]

        if not self._use_virtual_board:
            algorithms.append("FrontEndCommonApplicationRunner")

        # add any extra post algorithms as needed
        if self._extra_post_run_algorithms is not None:
            algorithms += self._extra_post_run_algorithms

        executor = None
        try:
            executor = PACMANAlgorithmExecutor(
                algorithms=algorithms, optional_algorithms=[], inputs=inputs,
                xml_paths=self._xml_paths, required_outputs=outputs,
                do_timings=self._do_timings, print_timings=self._print_timings)
            executor.execute_mapping()
            self._pacman_provenance.extract_provenance(executor)
        except KeyboardInterrupt:
            logger.error("User has aborted the simulation")
            self._shutdown()
            sys.exit(1)
        except Exception as e:

            logger.error(
                "An error has occurred during simulation")
            ex_type, ex_value, ex_traceback = sys.exc_info()
            for line in traceback.format_tb(ex_traceback):
                logger.error(line.strip())

            # if exception has an exception, print to system
            if isinstance(e, PacmanAlgorithmFailedToCompleteException):
                logger.error(e.exception)
            else:
                logger.error(e)

            logger.info("\n\nAttempting to extract data\n\n")

            # If an exception occurs during a run, attempt to get
            # information out of the simulation before shutting down
            try:
                self._recover_from_error(e, executor.get_items())
            except Exception:
                logger.error("Error when attempting to recover from error")
                traceback.print_exc()

            # if in debug mode, do not shut down machine
            in_debug_mode = self._config.get("Mode", "mode") == "Debug"
            if not in_debug_mode:
                self.stop(
                    turn_off_machine=False, clear_routing_tables=False,
                    clear_tags=False, extract_provenance_data=False,
                    extract_iobuf=False)

            # raise exception
            ex_type, ex_value, ex_traceback = sys.exc_info()
            raise ex_type, ex_value, ex_traceback

        self._last_run_outputs = executor.get_items()
        self._current_run_timesteps = total_run_timesteps
        self._last_run_outputs = executor.get_items()
        self._no_sync_changes = executor.get_item("NoSyncChanges")
        self._buffer_manager = executor.get_item("BufferManager")
        self._has_reset_last = False
        self._has_ran = True

    def _extract_provenance(self):
        if (self._config.get("Reports", "reportsEnabled") and
                self._config.get("Reports", "writeProvenanceData") and
                not self._use_virtual_board):

            if (self._last_run_outputs is not None and
                    not self._use_virtual_board):
                inputs = dict(self._last_run_outputs)
                algorithms = list()
                outputs = list()

                algorithms.append("FrontEndCommonGraphProvenanceGatherer")
                algorithms.append("FrontEndCommonPlacementsProvenanceGatherer")
                algorithms.append("FrontEndCommonRouterProvenanceGatherer")
                outputs.append("ProvenanceItems")

                executor = PACMANAlgorithmExecutor(
                    algorithms=algorithms, optional_algorithms=[],
                    inputs=inputs, xml_paths=self._xml_paths,
                    required_outputs=outputs, do_timings=self._do_timings,
                    print_timings=self._print_timings)
                executor.execute_mapping()
                self._pacman_provenance.extract_provenance(executor)
                provenance_outputs = executor.get_items()
                prov_items = executor.get_item("ProvenanceItems")
                prov_items.extend(self._pacman_provenance.data_items)
            else:
                prov_items = self._pacman_provenance.data_items
                if self._load_outputs is not None:
                    provenance_outputs = self._load_outputs
                else:
                    provenance_outputs = self._mapping_outputs

            if provenance_outputs is not None:
                self._write_provenance(provenance_outputs)
            if prov_items is not None:
                self._check_provenance(prov_items)

    def _write_provenance(self, provenance_outputs):
        """ Write provenance to disk
        """
        writer_algorithms = list()
        if self._provenance_format == "xml":
            writer_algorithms.append("FrontEndCommonProvenanceXMLWriter")
        elif self._provenance_format == "json":
            writer_algorithms.append("FrontEndCommonProvenanceJSONWriter")
        executor = PACMANAlgorithmExecutor(
            algorithms=writer_algorithms, optional_algorithms=[],
            inputs=provenance_outputs, xml_paths=self._xml_paths,
            required_outputs=[], do_timings=self._do_timings,
            print_timings=self._print_timings)
        executor.execute_mapping()

    def _recover_from_error(self, e, error_outputs):
        has_failed_to_start = isinstance(
            e, common_exceptions.ExecutableFailedToStartException)
        has_failed_to_end = isinstance(
            e, common_exceptions.ExecutableFailedToStopException)

        # If we have failed to start or end, get some extra data
        if has_failed_to_start or has_failed_to_end:
            is_rte = True
            if has_failed_to_end:
                is_rte = e.is_rte

            inputs = dict(error_outputs)
            inputs["FailedCoresSubsets"] = e.failed_core_subsets
            inputs["RanToken"] = True
            algorithms = list()
            outputs = list()

            # If there is not an RTE, ask the chips with an error to update
            # and get the provenance data
            if not is_rte:
                algorithms.append("FrontEndCommonChipProvenanceUpdater")
                algorithms.append("FrontEndCommonPlacementsProvenanceGatherer")

            # Get the other data
            algorithms.append("FrontEndCommonIOBufExtractor")
            algorithms.append("FrontEndCommonRouterProvenanceGatherer")

            # define outputs for the execution
            outputs.append("ProvenanceItems")
            outputs.append("IOBuffers")
            outputs.append("ErrorMessages")
            outputs.append("WarnMessages")

            executor = PACMANAlgorithmExecutor(
                algorithms=algorithms, optional_algorithms=[], inputs=inputs,
                xml_paths=self._xml_paths, required_outputs=outputs,
                do_timings=self._do_timings, print_timings=self._print_timings)
            executor.execute_mapping()

            self._write_provenance(executor.get_items())
            self._check_provenance(executor.get_item("ProvenanceItems"))
            self._write_iobuf(executor.get_item("IOBuffers"))
            self._print_iobuf(
                executor.get_item("ErrorMessages"),
                executor.get_item("WarnMessages"))
            self.stop(turn_off_machine=False, clear_routing_tables=False,
                      clear_tags=False, extract_provenance_data=False,
                      extract_iobuf=False)
            sys.exit(1)

    def _extract_iobuf(self):
        if (self._config.getboolean("Reports", "extract_iobuf") and
                self._last_run_outputs is not None and
                not self._use_virtual_board):
            inputs = self._last_run_outputs
            algorithms = ["FrontEndCommonIOBufExtractor"]
            outputs = ["IOBuffers"]
            executor = PACMANAlgorithmExecutor(
                algorithms=algorithms, optional_algorithms=[], inputs=inputs,
                xml_paths=self._xml_paths, required_outputs=outputs,
                do_timings=self._do_timings, print_timings=self._print_timings)
            executor.execute_mapping()
            self._write_iobuf(executor.get_item("IOBuffers"))

    def _write_iobuf(self, io_buffers):
        for iobuf in io_buffers:
            file_name = os.path.join(
                self._provenance_file_path,
                "{}_{}_{}.txt".format(iobuf.x, iobuf.y, iobuf.p))
            count = 2
            while os.path.exists(file_name):
                file_name = os.path.join(
                    self._provenance_file_path,
                    "{}_{}_{}-{}.txt".format(iobuf.x, iobuf.y, iobuf.p, count))
                count += 1
            writer = open(file_name, "w")
            writer.write(iobuf.iobuf)
            writer.close()

    @staticmethod
    def _print_iobuf(errors, warnings):
        for warning in warnings:
            logger.warn(warning)
        for error in errors:
            logger.error(error)

    def reset(self):
        """ Code that puts the simulation back at time zero
        """

        logger.info("Starting reset progress")
        if self._txrx is not None:

            # Get provenance up to this point
            self._extract_provenance()
            self._extract_iobuf()
            self._txrx.stop_application(self._app_id)

        # rewind the buffers from the buffer manager, to start at the beginning
        # of the simulation again and clear buffered out
        if self._buffer_manager is not None:
            self._buffer_manager.reset()

        # reset the current count of how many milliseconds the application
        # has ran for over multiple calls to run
        self._current_run_timesteps = 0

        # change number of resets as loading the binary again resets the sync\
        # to 0
        self._no_sync_changes = 0

        # sets the reset last flag to true, so that when run occurs, the tools
        # know to update the vertices which need to know a reset has occurred
        self._has_reset_last = True

    def _create_xml_paths(self, extra_algorithm_xml_paths):

        # add the extra xml files from the config file
        xml_paths = self._config.get("Mapping", "extra_xmls_paths")
        if xml_paths == "None":
            xml_paths = list()
        else:
            xml_paths = xml_paths.split(",")

        xml_paths.extend(
            helpful_functions.get_front_end_common_pacman_xml_paths())

        xml_paths.extend(extra_algorithm_xml_paths)
        return xml_paths

    def _detect_if_graph_has_changed(self, reset_flags=True):
        """ Iterates though the graph and looks changes
        """
        changed = False

        # if application graph is filled, check their changes
        if len(self._application_graph.vertices) != 0:
            for vertex in self._application_graph.vertices:
                if isinstance(vertex, AbstractChangableAfterRun):
                    if vertex.requires_mapping:
                        changed = True
                    if reset_flags:
                        vertex.mark_no_changes()
            for edge in self._application_graph.edges:
                if isinstance(edge, AbstractChangableAfterRun):
                    if edge.requires_mapping:
                        changed = True
                    if reset_flags:
                        edge.mark_no_changes()

        # if no application, but a machine graph, check for changes there
        elif len(self._machine_graph.vertices) != 0:
            for machine_vertex in self._machine_graph.vertices:
                if isinstance(machine_vertex, AbstractChangableAfterRun):
                    if machine_vertex.requires_mapping:
                        changed = True
                    if reset_flags:
                        machine_vertex.mark_no_changes()
            for machine_edge in self._machine_graph.edges:
                if isinstance(machine_edge, AbstractChangableAfterRun):
                    if machine_edge.requires_mapping:
                        changed = True
                    if reset_flags:
                        machine_edge.mark_no_changes()
        return changed

    @property
    def has_ran(self):
        """

        :return:
        """
        return self._has_ran

    @property
    def machine_time_step(self):
        """

        :return:
        """
        return self._machine_time_step

    @property
    def machine(self):
        """ The python machine object

        :rtype: :py:class:`spinn_machine.machine.Machine`
        """
        return self._get_machine()

    @property
    def no_machine_time_steps(self):
        """

        :return:
        """
        return self._no_machine_time_steps

    @property
    def timescale_factor(self):
        """

        :return:
        """
        return self._time_scale_factor

    @property
    def machine_graph(self):
        """

        :return:
        """
        return self._machine_graph

    @property
    def application_graph(self):
        """

        :return:
        """
        return self._application_graph

    @property
    def routing_infos(self):
        """

        :return:
        """
        return self._routing_infos

    @property
    def placements(self):
        """

        :return:
        """
        return self._placements

    @property
    def transceiver(self):
        """

        :return:
        """
        return self._txrx

    @property
    def graph_mapper(self):
        """

        :return:
        """
        return self._graph_mapper

    @property
    def buffer_manager(self):
        """ The buffer manager being used for loading/extracting buffers

        :return:
        """
        return self._buffer_manager

    @property
    def dsg_algorithm(self):
        """ The dsg algorithm used by the tools

        :return:
        """
        return self._dsg_algorithm

    @dsg_algorithm.setter
    def dsg_algorithm(self, new_dsg_algorithm):
        """ Set the dsg algorithm to be used by the tools

        :param new_dsg_algorithm: the new dsg algorithm name
        :return:
        """
        self._dsg_algorithm = new_dsg_algorithm

    @property
    def none_labelled_vertex_count(self):
        """ The number of times vertices have not been labelled.
        """
        return self._none_labelled_vertex_count

    def increment_none_labelled_vertex_count(self):
        """ Increment the number of new vertices which have not been labelled.
        """
        self._none_labelled_vertex_count += 1

    @property
    def none_labelled_edge_count(self):
        """ The number of times edges have not been labelled.
        """
        return self._none_labelled_edge_count

    def increment_none_labelled_edge_count(self):
        """ Increment the number of new edges which have not been labelled.
        """
        self._none_labelled_edge_count += 1

    @property
    def use_virtual_board(self):
        """ True if this run is using a virtual machine
        """
        return self._use_virtual_board

    def get_current_time(self):
        """

        :return:
        """
        if self._has_ran:
            return (
                float(self._current_run_timesteps) *
                (float(self._machine_time_step) / 1000.0))
        return 0.0

    def __repr__(self):
        return "general front end instance for machine {}"\
            .format(self._hostname)

    def add_application_vertex(self, vertex_to_add):
        """

        :param vertex_to_add: the vertex to add to the graph
        :return: None
        :raises: ConfigurationException when both graphs contain vertices
        """
        if (len(self._machine_graph.vertices) > 0 and
                self._graph_mapper is None):
            raise common_exceptions.ConfigurationException(
                "Cannot add vertices to both the machine and application"
                " graphs")
        if (isinstance(vertex_to_add, AbstractVirtualVertex) and
                self._machine is not None):
            raise common_exceptions.ConfigurationException(
                "A Virtual Vertex cannot be added after the machine has been"
                " created")
        self._application_graph.add_vertex(vertex_to_add)

    def add_machine_vertex(self, vertex):
        """

        :param vertex the vertex to add to the graph
        :return: None
        :raises: ConfigurationException when both graphs contain vertices
        """
        # check that there's no application vertices added so far
        if len(self._application_graph.vertices) > 0:
            raise common_exceptions.ConfigurationException(
                "Cannot add vertices to both the machine and application"
                " graphs")
        if (isinstance(vertex, AbstractVirtualVertex) and
                self._machine is not None):
            raise common_exceptions.ConfigurationException(
                "A Virtual Vertex cannot be added after the machine has been"
                " created")
        self._machine_graph.add_vertex(vertex)

    def add_application_edge(self, edge_to_add, partition_identifier):
        """

        :param edge_to_add:
        :param partition_identifier: the partition identifier for the outgoing
                    edge partition
        :return:
        """

        self._application_graph.add_edge(
            edge_to_add, partition_identifier)

    def add_machine_edge(self, edge, partition_id):
        """

        :param edge: the edge to add to the graph
        :param partition_id: the partition identifier for the outgoing
                    edge partition
        :return:
        """
        self._machine_graph.add_edge(edge, partition_id)

    def _shutdown(
            self, turn_off_machine=None, clear_routing_tables=None,
            clear_tags=None):

        # if not a virtual machine then shut down stuff on the board
        if not self._use_virtual_board:

            if turn_off_machine is None:
                turn_off_machine = self._config.getboolean(
                    "Machine", "turn_off_machine")

            if clear_routing_tables is None:
                clear_routing_tables = self._config.getboolean(
                    "Machine", "clear_routing_tables")

            if clear_tags is None:
                clear_tags = self._config.getboolean(
                    "Machine", "clear_tags")

            if self._txrx is not None:

                self._txrx.enable_reinjection(multicast=False)

                # if stopping on machine, clear iptags and
                if clear_tags:
                    for ip_tag in self._tags.ip_tags:
                        self._txrx.clear_ip_tag(
                            ip_tag.tag, board_address=ip_tag.board_address)
                    for reverse_ip_tag in self._tags.reverse_ip_tags:
                        self._txrx.clear_ip_tag(
                            reverse_ip_tag.tag,
                            board_address=reverse_ip_tag.board_address)

                # if clearing routing table entries, clear
                if clear_routing_tables:
                    for router_table in self._router_tables.routing_tables:
                        if not self._machine.get_chip_at(
                                router_table.x, router_table.y).virtual:
                            self._txrx.clear_multicast_routes(
                                router_table.x, router_table.y)

                # clear values
                self._no_sync_changes = 0

                # app stop command
                self._txrx.stop_application(self._app_id)

            if self._buffer_manager is not None:
                self._buffer_manager.stop()

            # stop the transceiver
            if self._txrx is not None:
                if turn_off_machine:
                    logger.info("Turning off machine")

                self._txrx.close(power_off_machine=turn_off_machine)

            if self._machine_allocation_controller is not None:
                self._machine_allocation_controller.close()

    def stop(self, turn_off_machine=None, clear_routing_tables=None,
             clear_tags=None, extract_provenance_data=True,
             extract_iobuf=True):
        """
        :param turn_off_machine: decides if the machine should be powered down\
            after running the execution. Note that this powers down all boards\
            connected to the BMP connections given to the transceiver
        :type turn_off_machine: bool
        :param clear_routing_tables: informs the tool chain if it\
            should turn off the clearing of the routing tables
        :type clear_routing_tables: bool
        :param clear_tags: informs the tool chain if it should clear the tags\
            off the machine at stop
        :type clear_tags: boolean
        :param extract_provenance_data: informs the tools if it should \
            try to extract provenance data.
        :type extract_provenance_data: bool
        :param extract_iobuf: tells the tools if it should try to \
            extract iobuf
        :type extract_iobuf: bool
        :return: None
        """

        if extract_provenance_data:
            self._extract_provenance()
        if extract_iobuf:
            self._extract_iobuf()

        self._shutdown(
            turn_off_machine, clear_routing_tables, clear_tags)

    def _add_socket_address(self, socket_address):
        """

        :param socket_address:
        :return:
        """
        self._database_socket_addresses.add(socket_address)

    @staticmethod
    def _check_provenance(items):
        """ Display any errors from provenance data
        """
        for item in items:
            if item.report:
                logger.warn(item.message)

    def _read_config(self, section, item):
        value = self._config.get(section, item)
        if value == "None":
            return None
        return value

    def _read_config_int(self, section, item):
        value = self._read_config(section, item)
        if value is None:
            return value
        return int(value)

    def _read_config_boolean(self, section, item):
        value = self._read_config(section, item)
        if value is None:
            return value
        return bool(value)
