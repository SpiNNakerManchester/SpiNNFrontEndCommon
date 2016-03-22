"""
main interface for the spinnaker tools
"""

# pacman imports
from pacman.model.partitionable_graph.partitionable_graph \
    import PartitionableGraph
from pacman.model.partitioned_graph.partitioned_graph import PartitionedGraph
from pacman.operations.pacman_algorithm_executor import PACMANAlgorithmExecutor
from pacman.exceptions import PacmanAlgorithmFailedToCompleteException

# common front end imports
from spinn_front_end_common.abstract_models.\
    abstract_has_first_machine_time_step import \
    AbstractHasFirstMachineTimeStep
from spinn_front_end_common.utilities import exceptions as common_exceptions
from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.interface.buffer_management\
    .buffer_models.abstract_receive_buffers_to_host \
    import AbstractReceiveBuffersToHost
from spinn_front_end_common.abstract_models.abstract_data_specable_vertex \
    import AbstractDataSpecableVertex
from spinn_front_end_common.utilities.utility_objs.executable_finder\
    import ExecutableFinder
from spinn_front_end_common.abstract_models.\
    abstract_recordable_interface import AbstractRecordableInterface
from spinn_front_end_common.interface.abstract_mappable_interface import \
    AbstractMappableInterface
from spinn_front_end_common.interface.provenance.pacman_provenance_extractor \
    import PacmanProvenanceExtractor


# general imports
from collections import defaultdict
import logging
import math
import os
import sys
import traceback

logger = logging.getLogger(__name__)

executable_finder = ExecutableFinder()


class SpinnakerMainInterface(object):
    """
    SpinnakerMainInterface: main interface into the tools logic flow
    """

    def __init__(self, this_config, version, this_executable_finder,
                 host_name=None, graph_label=None,
                 database_socket_addresses=None,
                 extra_algorithm_xml_paths=None,
                 extra_mapping_inputs=None, extra_mapping_algorithms=None,
                 extra_pre_run_algorithms=None, extra_post_run_algorithms=None):

        # global params
        global config
        config = this_config
        global executable_finder
        executable_finder = this_executable_finder

        self._hostname = host_name
        self._version = version
        self._spalloc_server = None
        self._remote_spinnaker_url = None
        self._machine_allocation_controller = None

        # update graph label if needed
        if graph_label is None:
            graph_label = "Application_graph"

        # pacman objects
        self._partitionable_graph = PartitionableGraph(label=graph_label)
        self._partitioned_graph = PartitionedGraph(label=graph_label)
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
        self._mapping_outputs = None
        self._load_outputs = None
        self._last_run_outputs = None
        self._pacman_provenance = PacmanProvenanceExtractor()
        self._xml_paths = self._create_xml_paths(extra_algorithm_xml_paths)

        # extra algorithms and inputs for runs, should disappear in future
        #  releases
        self._extra_mapping_algorithms = list(extra_mapping_algorithms)
        self._extra_mapping_inputs = dict(extra_mapping_inputs)
        self._extra_pre_run_algorithms = list(extra_pre_run_algorithms)
        self._extra_post_run_algorithms = list(extra_post_run_algorithms)
        self._dsg_algorithm = None
        self._dsg_algorithm = \
            "FrontEndCommonPartitionableGraphDataSpecificationWriter"

        # vertex label safety (used by reports mainly)
        self._none_labelled_vertex_count = 0
        self._none_labelled_edge_count = 0

        # database objects
        self._database_socket_addresses = set()
        if database_socket_addresses is not None:
            self._database_socket_addresses.union(database_socket_addresses)
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

        self._app_id = config.getint("Machine", "appID")

        # set up reports default folder
        self._report_default_directory, this_run_time_string = \
            helpful_functions.set_up_report_specifics(
                default_report_file_path=config.get(
                    "Reports", "defaultReportFilePath"),
                max_reports_kept=config.getint(
                    "Reports", "max_reports_kept"),
                app_id=self._app_id)

        # set up application report folder
        self._app_data_runtime_folder = \
            helpful_functions.set_up_output_application_data_specifics(
                max_application_binaries_kept=config.getint(
                    "Reports", "max_application_binaries_kept"),
                where_to_write_application_data_files=config.get(
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
        self._do_timings = config.getboolean(
            "Reports", "writeAlgorithmTimings")
        self._print_timings = config.getboolean(
            "Reports", "display_algorithm_timings")
        self._provenance_format = config.get("Reports", "provenance_format")
        if self._provenance_format not in ["xml", "json"]:
            raise Exception("Unknown provenance format: {}".format(
                self._provenance_format))
        self._exec_dse_on_host = config.getboolean(
            "SpecExecution", "specExecOnHost")

        # set up machine targeted data
        self._use_virtual_board = config.getboolean("Machine", "virtual_board")

        # log appid to end user
        logger.info("Setting appID to %d." % self._app_id)

    def set_up_machine_specifics(self, hostname):
        """
        helper method for adding machine specifics for the different modes.
        :param hostname:
        :return:
        """
        if hostname is not None:
            self._hostname = hostname
            logger.warn("The machine name from pyNN setup is overriding the "
                        "machine name defined in the spynnaker.cfg file")
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
                "A SpiNNaker machine must be specified in spynnaker.cfg.")

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
                "in spynnaker.cfg")

        if self._spalloc_server is not None:
            if self._read_config("Machine", "spalloc_user") is None:
                raise Exception(
                    "A spalloc_user must be specified with a spalloc_server")

    def run(self, run_time):
        """

        :param run_time: the runtime expected to run for in milliseconds.
        :return: None
        """
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
        if self._has_ran and self._machine_allocation_controller is not None:
            self._machine_allocation_controller.extend_allocation(
                total_run_time)

        # If we have never run before, or the graph has changed,
        # start by performing mapping
        application_graph_changed = self._detect_if_graph_has_changed(True)
        if not self._has_ran or application_graph_changed:
            if (application_graph_changed and self._has_ran and
                    not self._has_reset_last):
                raise NotImplementedError(
                    "The network cannot be changed between runs without"
                    " resetting")
            self._do_mapping(run_time, n_machine_time_steps, total_run_time)

        # Work out an array of timesteps to perform
        if not config.getboolean("Buffers", "use_auto_pause_and_resume"):

            # Not currently possible to run the second time for more than the
            # first time without auto pause and resume
            if (self._minimum_step_generated is not None and
                    self._minimum_step_generated < n_machine_time_steps):
                raise common_exceptions.ConfigurationException(
                    "Second and subsequent run time must be less than or equal"
                    " to the first run time")

            steps = [n_machine_time_steps]
            self._minimum_step_generated = steps[0]
        else:

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
            if application_graph_changed:
                self._do_data_generation(steps[0])

            # If we are using a virtual board, don't load
            if not self._use_virtual_board:
                self._do_load()

        # Run for each of the given steps
        for step in steps:
            self._do_run(step)

    def _deduce_number_of_iterations(self, n_machine_time_steps):

        # Go through the placements and find how much SDRAM is available
        # on each chip
        sdram_tracker = dict()
        vertex_by_chip = defaultdict(list)
        for placement in self._placements.placements:
            vertex = placement.subvertex
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

    def _update_n_machine_time_steps(self, n_machine_time_steps):
        for vertex in self._partitionable_graph.vertices:
            if isinstance(vertex, AbstractDataSpecableVertex):
                vertex.set_no_machine_time_steps(n_machine_time_steps)

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
            for vertex in self._partitionable_graph.vertices:
                if (isinstance(vertex, AbstractRecordableInterface)
                        and vertex.is_recording()):
                    raise common_exceptions.ConfigurationException(
                        "recording a vertex when set to infinite runtime "
                        "is not currently supported")
            for vertex in self._partitioned_graph.subvertices:
                if (isinstance(vertex, AbstractRecordableInterface)
                        and vertex.is_recording()):
                    raise common_exceptions.ConfigurationException(
                        "recording a vertex when set to infinite runtime "
                        "is not currently supported")
        return total_run_timesteps

    def _do_mapping(self, run_time, n_machine_time_steps, total_run_time):

        # Set the initial n_machine_time_steps to all of them for mapping
        # (note that the underlying vertices will know about
        # auto-pause-and-resume and so they will work correctly here regardless
        # of the setting)
        self._update_n_machine_time_steps(n_machine_time_steps)

        # update inputs with extra mapping inputs if required
        if self._extra_mapping_inputs is not None:
            inputs = dict(self._extra_mapping_inputs)
        else:
            inputs = dict()

        inputs["RunTime"] = run_time
        inputs["TotalRunTime"] = total_run_time
        inputs["PostSimulationOverrunBeforeError"] = config.getint(
            "Machine", "post_simulation_overrun_before_error")

        # handle graph additions
        if len(self.partitionable_graph.vertices) != 0:
            inputs["MemoryPartitionableGraph"] = self._partitionable_graph
        elif len(self._partitioned_graph.subvertices) != 0:
            inputs['MemoryPartitionedGraph'] = self._partitioned_graph
        else:
            raise common_exceptions.ConfigurationException(
                "There needs to be a graph which contains at least one vertex"
                " for the tool chain to map anything. ")

        inputs['ReportFolder'] = self._report_default_directory
        inputs["ApplicationDataFolder"] = self._app_data_runtime_folder
        inputs["APPID"] = self._app_id
        inputs["DSEAppID"] = config.getint("Machine", "DSEAppID")
        inputs["ExecDSEOnHostFlag"] = self._exec_dse_on_host
        inputs["TimeScaleFactor"] = self._time_scale_factor
        inputs["MachineTimeStep"] = self._machine_time_step
        inputs["DatabaseSocketAddresses"] = self._database_socket_addresses
        inputs["DatabaseWaitOnConfirmationFlag"] = config.getboolean(
            "Database", "wait_on_confirmation")
        inputs["WriteCheckerFlag"] = config.getboolean(
            "Mode", "verify_writes")
        inputs["WriteTextSpecsFlag"] = config.getboolean(
            "Reports", "writeTextSpecs")
        inputs["ExecutableFinder"] = executable_finder
        inputs["MachineHasWrapAroundsFlag"] = self._read_config_boolean(
            "Machine", "requires_wrap_arounds")
        inputs["UserCreateDatabaseFlag"] = config.get(
            "Database", "create_database")
        inputs["SendStartNotifications"] = config.getboolean(
            "Database", "send_start_notification")

        # add paths for each file based version
        inputs["FileCoreAllocationsFilePath"] = os.path.join(
            self._json_folder, "core_allocations.json")
        inputs["FileSDRAMAllocationsFilePath"] = os.path.join(
            self._json_folder, "sdram_allocations.json")
        inputs["FileMachineFilePath"] = os.path.join(
            self._json_folder, "machine.json")
        inputs["FilePartitionedGraphFilePath"] = os.path.join(
            self._json_folder, "partitioned_graph.json")
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

        # handle algorithms and inputs for finding machine
        self._generate_inputs_and_algorithms_for_getting_machine(
            algorithms, inputs)

        # Add reports
        if config.getboolean("Reports", "reportsEnabled"):
            if config.getboolean("Reports", "writeTagAllocationReports"):
                algorithms.append("TagReport")
            if config.getboolean("Reports", "writeRouterInfoReport"):
                algorithms.append("routingInfoReports")
            if config.getboolean("Reports", "writeRouterReports"):
                algorithms.append("RouterReports")
            if config.getboolean("Reports", "writeRoutingTableReports"):
                algorithms.append("unCompressedRoutingTableReports")
                algorithms.append("compressedRoutingTableReports")
                algorithms.append("comparisonOfRoutingTablesReport")

            # only add partitioner report if using a partitionable graph
            if (config.getboolean("Reports", "writePartitionerReports") and
                    len(self._partitionable_graph.vertices) != 0):
                algorithms.append("PartitionerReport")

            # only add write placer report with partitionable graph when
            # there's partitionable vertices
            if (config.getboolean(
                    "Reports", "writePlacerReportWithPartitionable") and
                    len(self._partitionable_graph.vertices) != 0):
                algorithms.append("PlacerReportWithPartitionableGraph")

            if config.getboolean(
                    "Reports", "writePlacerReportWithoutPartitionable"):
                algorithms.append("PlacerReportWithoutPartitionableGraph")

            # only add network specification partitionable report if there's
            # partitionable vertices.
            if (config.getboolean("Reports", "writeNetworkSpecificationReport")
                    and len(self._partitionable_graph.vertices) != 0):
                algorithms.append(
                    "FrontEndCommonNetworkSpecificationPartitionableReport")

        # only add the partitioner if there is a partitionable graph to use.
        if len(self._partitionable_graph.vertices) != 0:
            algorithms.extend(config.get(
                "Mapping",
                "partitionable_to_partitioned_algorithms").split(","))

        # If using an allocator, we will need to do chip allocation again
        # after partitioning
        if not self._use_virtual_board:
            algorithms.append("MallocBasedChipIDAllocator")

        algorithms.extend(config.get(
            "Mapping", "partitioned_to_machine_algorithms").split(","))

        # decide upon the outputs based off if there is a
        # partitionable graph that has vertices added to it.
        if len(self._partitionable_graph.vertices) != 0:
            outputs = [
                "MemoryPlacements", "MemoryRoutingTables",
                "MemoryTags", "MemoryGraphMapper", "MemoryPartitionedGraph",
                "MemoryMachine", "MemoryRoutingInfos"]
        else:
            outputs = [
                "MemoryPlacements", "MemoryRoutingTables",
                "MemoryTags", "MemoryPartitionedGraph", "MemoryMachine",
                "MemoryRoutingInfos"]

        # if not using a virtual board, need the spinnman interface
        # and ip-address
        if not self._use_virtual_board:
            outputs.append("MemoryTransceiver")
            outputs.append("IPAddress")
        if (self._machine_allocation_controller is None and (
                self._spalloc_server is not None or
                self._remote_spinnaker_url is not None)):
            outputs.append("MachineAllocationController")

        # Execute the mapping algorithms
        executor = PACMANAlgorithmExecutor(
            algorithms, [], inputs, self._xml_paths, outputs, self._do_timings,
            self._print_timings)
        executor.execute_mapping()
        self._mapping_outputs = executor.get_items()
        self._pacman_provenance.extract_provenance(executor)

        # Get the outputs needed
        if not self._use_virtual_board:
            self._txrx = executor.get_item("MemoryTransceiver")
            self._ip_address = executor.get_item("IPAddress")
        self._placements = executor.get_item("MemoryPlacements")
        self._router_tables = executor.get_item("MemoryRoutingTables")
        self._tags = executor.get_item("MemoryTags")
        self._graph_mapper = executor.get_item("MemoryGraphMapper")
        self._partitioned_graph = executor.get_item("MemoryPartitionedGraph")
        self._machine = executor.get_item("MemoryMachine")
        self._routing_infos = executor.get_item("MemoryRoutingInfos")

        if (self._machine_allocation_controller is None and (
                self._spalloc_server is not None or
                self._remote_spinnaker_url is not None)):
            self._machine_allocation_controller = executor.get_item(
                "MachineAllocationController")

    def _generate_inputs_and_algorithms_for_getting_machine(
            self, algorithms, inputs):

        # general machine inputs
        inputs["ResetMachineOnStartupFlag"] = config.getboolean(
            "Machine", "reset_machine_on_startup")

        # add reinjection flag
        inputs["EnableReinjectionFlag"] = config.getboolean(
            "Machine", "enable_reinjection")

        # add max sdram size which we're going to allow (debug purposes)
        inputs["MaxSDRAMSize"] = self._read_config_int(
            "Machine", "max_sdram_allowed_per_chip")

        # if using spalloc system
        if self._spalloc_server is not None:
            inputs["SpallocServer"] = self._spalloc_server
            inputs["SpallocPort"] = self._read_config_int(
                "Machine", "spalloc_port")
            inputs["SpallocUser"] = self._read_config(
                "Machine", "spalloc_user")

        # if using HBP server system
        if self._remote_spinnaker_url is not None:
            inputs["RemoteSpinnakerUrl"] = self._remote_spinnaker_url

        # Handle virtual machine, which will also be needed if an allocation
        # server is to be used
        if (self._machine is None and self._txrx is None and (
                self._use_virtual_board or self._spalloc_server is not None or
                self._remote_spinnaker_url is not None)):
            if self._spalloc_server is not None:
                algorithms.append("FrontEndCommonSpallocMaxMachineGenerator")
            elif self._remote_spinnaker_url is not None:
                algorithms.append("FrontEndCommonHBPMaxMachineGenerator")
            algorithms.append("FrontEndCommonVirtualMachineGenerator")
            algorithms.append("MallocBasedChipIDAllocator")
            if config.getboolean("Machine", "enable_reinjection"):
                inputs["CPUsPerVirtualChip"] = 15
            else:
                inputs["CPUsPerVirtualChip"] = 16
        elif self._hostname is not None:
            self._add_machine_inputs(inputs)

        # Only do allocation or generate a machine if not virtual
        if not self._use_virtual_board:
            if self._machine is None and self._txrx is None:
                if self._spalloc_server is not None:
                    algorithms.append("FrontEndCommonSpallocAllocator")
                elif self._remote_spinnaker_url is not None:
                    algorithms.append("FrontEndCommonHBPAllocator")

                algorithms.append("FrontEndCommonMachineGenerator")
            else:
                inputs["MemoryMachine"] = self._machine
                inputs["MemoryTransceiver"] = self._txrx
                inputs["IPAddress"] = self._ip_address
        else:
            self._add_machine_inputs(inputs)
            inputs["MemoryTransceiver"] = None

    def _add_machine_inputs(self, inputs):
        inputs['IPAddress'] = self._hostname
        inputs["BMPDetails"] = self._read_config("Machine", "bmp_names")
        inputs["DownedChipsDetails"] = config.get("Machine", "down_chips")
        inputs["DownedCoresDetails"] = config.get("Machine", "down_cores")
        inputs["BoardVersion"] = self._read_config_int(
            "Machine", "version")
        inputs["NumberOfBoards"] = self._read_config_int(
            "Machine", "number_of_boards")
        inputs["MachineWidth"] = self._read_config_int(
            "Machine", "width")
        inputs["MachineHeight"] = self._read_config_int(
            "Machine", "height")
        inputs["AutoDetectBMPFlag"] = config.getboolean(
            "Machine", "auto_detect_bmp")
        inputs["ScampConnectionData"] = self._read_config(
            "Machine", "scamp_connections_data")
        inputs["BootPortNum"] = self._read_config_int(
            "Machine", "boot_connection_port_num")

    def _do_data_generation(self, n_machine_time_steps):

        # Update the machine timesteps again for the data generation
        self._update_n_machine_time_steps(n_machine_time_steps)

        # The initial inputs are the mapping outputs
        inputs = dict(self._mapping_outputs)

        # Run the data generation algorithms
        algorithms = [self._dsg_algorithm]

        executor = PACMANAlgorithmExecutor(
            algorithms, [], inputs, self._xml_paths, [], self._do_timings,
            self._print_timings)
        executor.execute_mapping()
        self._mapping_outputs = executor.get_items()
        self._pacman_provenance.extract_provenance(executor)

    def _do_load(self):

        # The initial inputs are the mapping outputs
        inputs = dict(self._mapping_outputs)
        inputs["WriteMemoryMapReportFlag"] = (
            config.getboolean("Reports", "reportsEnabled") and
            config.getboolean("Reports", "writeMemoryMapReport")
        )

        algorithms = list()
        optional_algorithms = list()
        optional_algorithms.append("FrontEndCommonRoutingTableLoader")
        optional_algorithms.append("FrontEndCommonTagsLoader")
        if self._exec_dse_on_host:
            optional_algorithms.append(
                "FrontEndCommonPartitionableGraphHostExecuteDataSpecification")
            if config.getboolean("Reports", "writeMemoryMapReport"):
                optional_algorithms.append(
                    "FrontEndCommonMemoryMapOnHostReport")
        else:
            optional_algorithms.append(
                "FrontEndCommonPartitionableGraphMachineExecuteDataSpecification")  # @IgnorePep8
            if config.getboolean("Reports", "writeMemoryMapReport"):
                optional_algorithms.append(
                    "FrontEndCommonMemoryMapOnChipReport")
        optional_algorithms.append("FrontEndCommonLoadExecutableImages")

        outputs = [
            "LoadedReverseIPTagsToken", "LoadedIPTagsToken",
            "LoadedRoutingTablesToken", "LoadBinariesToken",
            "LoadedApplicationDataToken"
        ]

        executor = PACMANAlgorithmExecutor(
            algorithms, optional_algorithms, inputs, self._xml_paths,
            outputs, self._do_timings, self._print_timings)
        executor.execute_mapping()
        self._load_outputs = executor.get_items()
        self._pacman_provenance.extract_provenance(executor)

    def _do_run(self, n_machine_time_steps):

        # calculate number of machine time steps
        total_run_timesteps = self._calculate_number_of_machine_time_steps(
            n_machine_time_steps)
        self._update_n_machine_time_steps(total_run_timesteps)
        run_time = (
            n_machine_time_steps * (float(self._machine_time_step) / 1000.0))

        # Calculate the first machine time step to start from and set this
        # where necessary
        first_machine_time_step = self._current_run_timesteps
        for vertex in self._partitionable_graph.vertices:
            if isinstance(vertex, AbstractHasFirstMachineTimeStep):
                vertex.set_first_machine_time_step(first_machine_time_step)

        # if running again, load the outputs from last load vs last run
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

        # update algorithm list with extra pre algorithms if needed
        if self._extra_pre_run_algorithms is not None:
            algorithms = list(self._extra_pre_run_algorithms)
        else:
            algorithms = list()

        # Create a buffer manager if there isn't one already
        if self._buffer_manager is None:
            inputs["WriteReloadFilesFlag"] = (
                config.getboolean("Reports", "reportsEnabled") and
                config.getboolean("Reports", "writeReloadSteps")
            )
            algorithms.append("FrontEndCommonBufferManagerCreator")
        else:
            inputs["BufferManager"] = self._buffer_manager

        if not self._use_virtual_board:
            algorithms.append("FrontEndCommonChipRuntimeUpdater")

        # Add the database writer in case it is needed
        algorithms.append("FrontEndCommonNotificationProtocol")

        # Sort out reload if needed
        if config.getboolean("Reports", "writeReloadSteps"):
            if not self._has_ran:
                algorithms.append("FrontEndCommonReloadScriptCreator")
                if self._use_virtual_board:
                    logger.warn(
                        "A reload script will be created, but as you are using"
                        " a virtual board, you will need to edit the "
                        " machine_name before you use it")
            else:
                logger.warn(
                    "The reload script cannot handle multi-runs, nor can"
                    "it handle resets, therefore it will only contain the "
                    "initial run")

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
                algorithms, [], inputs, self._xml_paths, outputs,
                self._do_timings, self._print_timings)
            executor.execute_mapping()
            self._pacman_provenance.extract_provenance(executor)
        except PacmanAlgorithmFailedToCompleteException as e:

            logger.error(
                "An error has occurred during simulation - "
                "attempting to extract data")
            for line in traceback.format_tb(e.traceback):
                logger.error(line.strip())
            logger.error(e.exception)

            # If an exception occurs during a run, attempt to get
            # information out of the simulation before shutting down
            try:
                self._recover_from_error(e, executor.get_items())
            except Exception:
                self.stop()
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
        if (config.get("Reports", "reportsEnabled") and
                config.get("Reports", "writeProvenanceData") and
                not self._use_virtual_board):

            if (self._last_run_outputs is not None and
                    not self._use_virtual_board):
                inputs = dict(self._last_run_outputs)
                algorithms = list()
                outputs = list()

                algorithms.append("FrontEndCommonPlacementsProvenanceGatherer")
                algorithms.append("FrontEndCommonRouterProvenanceGatherer")
                outputs.append("ProvenanceItems")

                executor = PACMANAlgorithmExecutor(
                    algorithms, [], inputs, self._xml_paths, outputs,
                    self._do_timings, self._print_timings)
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
            writer_algorithms, [], provenance_outputs, self._xml_paths,
            [], self._do_timings, self._print_timings)
        executor.execute_mapping()

    def _recover_from_error(self, e, error_outputs):
        error = e.exception
        has_failed_to_start = isinstance(
            error, common_exceptions.ExecutableFailedToStartException)
        has_failed_to_end = isinstance(
            error, common_exceptions.ExecutableFailedToStopException)

        # If we have failed to start or end, get some extra data
        if has_failed_to_start or has_failed_to_end:
            is_rte = True
            if has_failed_to_end:
                is_rte = error.is_rte

            inputs = dict(error_outputs)
            inputs["FailedCoresSubsets"] = error.failed_core_subsets
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
                algorithms, [], inputs, self._xml_paths, outputs,
                self._do_timings, self._print_timings)
            executor.execute_mapping()

            self._write_provenance(executor.get_items())
            self._check_provenance(executor.get_item("ProvenanceItems"))
            self._write_iobuf(executor.get_item("IOBuffers"))
            self._print_iobuf(
                executor.get_item("ErrorMessages"),
                executor.get_item("WarnMessages"))

    def _extract_iobuf(self):
        if (config.getboolean("Reports", "extract_iobuf") and
                self._last_run_outputs is not None and
                not self._use_virtual_board):
            inputs = self._last_run_outputs
            algorithms = ["FrontEndCommonIOBufExtractor"]
            outputs = ["IOBuffers"]
            executor = PACMANAlgorithmExecutor(
                algorithms, [], inputs, self._xml_paths, outputs,
                self._do_timings, self._print_timings)
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

    @staticmethod
    def _create_xml_paths(extra_algorithm_xml_paths):

        # add the extra xml files from the config file
        xml_paths = config.get("Mapping", "extra_xmls_paths")
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
        # if partitionable graph is filled, check their changes
        if len(self._partitionable_graph.vertices) != 0:
            for partitionable_vertex in self._partitionable_graph.vertices:
                if isinstance(partitionable_vertex, AbstractMappableInterface):
                    if partitionable_vertex.requires_mapping:
                        changed = True
                    if reset_flags:
                        partitionable_vertex.mark_no_changes()
            for partitionable_edge in self._partitionable_graph.edges:
                if isinstance(partitionable_edge, AbstractMappableInterface):
                    if partitionable_edge.requires_mapping:
                        changed = True
                    if reset_flags:
                        partitionable_edge.mark_no_changes()
        # if no partitionable, but a partitioned graph, check for changes there
        elif len(self._partitioned_graph.subvertices) != 0:
            for partitioned_vertex in self._partitioned_graph.subvertices:
                if isinstance(partitioned_vertex, AbstractMappableInterface):
                    if partitioned_vertex.requires_mapping:
                        changed = True
                    if reset_flags:
                        partitioned_vertex.mark_no_changes()
            for partitioned_edge in self._partitioned_graph.subedges:
                if isinstance(partitioned_edge, AbstractMappableInterface):
                    if partitioned_edge.requires_mapping:
                        changed = True
                    if reset_flags:
                        partitioned_edge.mark_no_changes()
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
    def partitioned_graph(self):
        """

        :return:
        """
        return self._partitioned_graph

    @property
    def partitionable_graph(self):
        """

        :return:
        """
        return self._partitionable_graph

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
        """
        returns the buffer manager being used for loading/extracting buffers
        :return:
        """
        return self._buffer_manager

    @property
    def dsg_algorithm(self):
        """
        returns the dsg algorithm used by the tools
        :return:
        """
        return self._dsg_algorithm

    @dsg_algorithm.setter
    def dsg_algorithm(self, new_dsg_algorithm):
        """
        sets the dsg algorithm to be used by the tools
        :param new_dsg_algorithm: the new dsg algorithm name
        :return:
        """
        self._dsg_algorithm = new_dsg_algorithm

    @property
    def none_labelled_vertex_count(self):
        """
        the number of times vertices have not been labelled.
        :return: the number of times the vertices have not been labelled
        """
        return self._none_labelled_vertex_count

    def increment_none_labelled_vertex_count(self):
        """
        increments the number of new vertices which have not been labelled.
        :return: None
        """
        self._none_labelled_vertex_count += 1

    @property
    def none_labelled_edge_count(self):
        """
        the number of times vertices have not been labelled.
        :return: the number of times the vertices have not been labelled
        """
        return self._none_labelled_edge_count

    def increment_none_labelled_edge_count(self):
        """
        increments the number of new edges which have not been labelled.
        :return: None
        """
        self._none_labelled_edge_count += 1

    @property
    def use_virtual_board(self):
        """
        returns bool that states if this run is suing a virtual machine
        :return:
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

    def add_partitionable_vertex(self, vertex_to_add):
        """

        :param vertex_to_add: the partitionable vertex to add to the graph
        :return: None
        :raises: ConfigurationException when both graphs contain vertices
        """
        if len(self._partitioned_graph.subvertices) > 0:
            raise common_exceptions.ConfigurationException(
                "The partitioned graph has already got some vertices, and "
                "therefore the application cannot be executed correctly due "
                "to not knowing how these two graphs interact with each "
                "other. Please rectify and try again")
        self._partitionable_graph.add_vertex(vertex_to_add)

    def add_partitioned_vertex(self, vertex):
        """

        :param vertex the partitioned vertex to add to the graph
        :return: None
        :raises: ConfigurationException when both graphs contain vertices
        """
        # check that there's no partitioned vertices added so far
        if len(self._partitionable_graph.vertices) > 0:
            raise common_exceptions.ConfigurationException(
                "The partitionable graph has already got some vertices, and "
                "therefore the application cannot be executed correctly due "
                "to not knowing how these two graphs interact with each "
                "other. Please rectify and try again")
        self._partitioned_graph.add_subvertex(vertex)

    def add_partitionable_edge(
            self, edge_to_add, partition_identifier=None,
            partition_constraints=None):
        """

        :param edge_to_add:
        :param partition_identifier: the partition identifier for the outgoing
                    edge partition
        :param partition_constraints: the constraints of a partition
        associated with this edge
        :return:
        """

        self._partitionable_graph.add_edge(
            edge_to_add, partition_identifier, partition_constraints)

    def add_partitioned_edge(
            self, edge, partition_id=None, partition_constraints=None):
        """

        :param edge: the partitioned edge to add to the partitioned graph
        :param partition_constraints:the constraints of a partition
        associated with this edge
        :param partition_id: the partition identifier for the outgoing
                    edge partition
        :return:
        """
        self._partitioned_graph.add_subedge(
            edge, partition_id, partition_constraints)

    def _shutdown(
            self, turn_off_machine=None, clear_routing_tables=None,
            clear_tags=None):

        # if not a virtual machine, then shut down stuff on the board
        if not self._use_virtual_board:

            if turn_off_machine is None:
                turn_off_machine = config.getboolean(
                    "Machine", "turn_off_machine")

            if clear_routing_tables is None:
                clear_routing_tables = config.getboolean(
                    "Machine", "clear_routing_tables")

            if clear_tags is None:
                clear_tags = config.getboolean("Machine", "clear_tags")

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
             clear_tags=None):
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
        :return: None
        """

        self._extract_provenance()
        self._extract_iobuf()

        self._shutdown(turn_off_machine, clear_routing_tables, clear_tags)

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

    @staticmethod
    def _read_config(section, item):
        value = config.get(section, item)
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
