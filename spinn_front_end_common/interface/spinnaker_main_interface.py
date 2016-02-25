"""
SpinnakerMainInterface
"""

# pacman imports
from pacman.interfaces.abstract_provides_provenance_data import \
    AbstractProvidesProvenanceData
from pacman.model.partitionable_graph.partitionable_graph import \
    PartitionableGraph
from pacman.model.partitioned_graph.partitioned_graph import PartitionedGraph
from pacman.operations import algorithm_reports as pacman_algorithm_reports
from pacman.operations.pacman_algorithm_executor import PACMANAlgorithmExecutor
from pacman.utilities.utility_objs.provenance_data_item import \
    ProvenanceDataItem

# common front end imports
from spinn_front_end_common.interface.abstract_mappable_interface import \
    AbstractMappableInterface
from spinn_front_end_common.interface.interface_functions. \
    front_end_common_execute_mapper import \
    FrontEndCommonExecuteMapper
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities.utility_objs. \
    provenance_data_items import ProvenanceDataItems
from spinn_front_end_common.utilities.utility_objs.report_states \
    import ReportState
from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.interface import interface_functions

# general imports
from abc import ABCMeta
from six import add_metaclass
from abc import abstractmethod
import logging
import os

# global objects
logger = logging.getLogger(__name__)
executable_finder = None
config = None

@add_metaclass(ABCMeta)
class SpinnakerMainInterface(AbstractProvidesProvenanceData):
    """
    SpinnakerMainInterface: central entrance for front ends if desired
    """

    def __init__(
            self, this_config, version, this_executable_finder, host_name=None,
            graph_label=None, database_socket_addresses=None,
            extra_algorithm_xml_paths=None,
            extra_algorithms_for_auto_pause_and_resume=None):

        # inheritance
        AbstractProvidesProvenanceData.__init__(self)

        # global params
        global config
        config = this_config
        global executable_finder
        executable_finder = this_executable_finder

        # start data holders
        self._hostname = host_name
        self._version = version

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
        self._reports_states = None
        self._app_id = None
        self._buffer_manager = None
        self._extra_algorithm_xml_paths = extra_algorithm_xml_paths

        # vertex label safety (used by reports mainly)
        self._non_labelled_vertex_count = 0
        self._none_labelled_edge_count = 0

        # database objects
        self._database_socket_addresses = set()
        if database_socket_addresses is not None:
            self._database_socket_addresses.union(database_socket_addresses)
        self._database_interface = None
        self._create_database = None
        self._database_file_path = None

        # holder for the executable targets (which we will need for reset and
        # pause and resume functionality
        self._executable_targets = None
        self._provenance_data_items = ProvenanceDataItems()
        self._provenance_file_path = None

        # holders for data needed for reset when nothing changes in the
        # application graph
        self._processor_to_app_data_base_address_mapper = None
        self._placement_to_app_data_file_paths = None
        self._dsg_targets = None

        # holder for timing related values
        self._has_ran = False
        self._has_reset_last = False
        self._current_run_ms = 0
        self._no_machine_time_steps = None
        self._machine_time_step = None
        self._no_sync_changes = 0
        self._steps = None
        self._original_first_run = None

        # holder for algorithms to check for prov if crashed
        algorithms_listing = \
            config.get("Reports", "algorithms_to_get_prov_after_crash")
        self._algorithms_to_catch_prov_on_crash = algorithms_listing.split(",")

        # state that's needed the first time around
        if self._app_id is None:
            self._app_id = config.getint("Machine", "appID")
            self._dse_app_id = config.getint("Machine", "DSEappID")

            if config.getboolean("Reports", "reportsEnabled"):
                self._reports_states = ReportState(
                    config.getboolean("Reports", "writePartitionerReports"),
                    config.getboolean("Reports",
                                      "writePlacerReportWithPartitionable"),
                    config.getboolean("Reports",
                                      "writePlacerReportWithoutPartitionable"),
                    config.getboolean("Reports", "writeRouterReports"),
                    config.getboolean("Reports", "writeRouterInfoReport"),
                    config.getboolean("Reports", "writeTextSpecs"),
                    config.getboolean("Reports", "writeReloadSteps"),
                    config.getboolean("Reports", "writeTransceiverReport"),
                    config.getboolean("Reports", "outputTimesForSections"),
                    config.getboolean("Reports", "writeTagAllocationReports"),
                    config.getboolean("Reports", "writeMemoryMapReport"))

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

            # set up provenance data folder
            self._provenance_file_path = \
                os.path.join(self._report_default_directory, "provenance_data")
            if not os.path.exists(self._provenance_file_path):
                os.mkdir(self._provenance_file_path)

            self._exec_dse_on_host = config.getboolean(
                "SpecExecution", "specExecOnHost")

        # if your using the auto pause and resume, then add the inputs needed
        # for this functionality.
        self._using_auto_pause_and_resume = \
            config.getboolean("Mode", "use_auto_pause_and_resume")
        self._extra_algorithms_for_auto_pause_and_resume = \
            extra_algorithms_for_auto_pause_and_resume

        logger.info("Setting appID to %d." % self._app_id)

    def run(self, run_time):
        """

        :param run_time:
        :return:
        """
        logger.info("Starting execution process")

        if self._original_first_run is None:
            self._original_first_run = run_time

        # get inputs
        inputs, application_graph_changed, uses_auto_pause_and_resume = \
            self._create_pacman_executor_inputs(run_time)

        if (self._original_first_run < run_time and
                not uses_auto_pause_and_resume):
            raise exceptions.ConfigurationException(
                "Currently spynnaker cannot handle a runtime greater than what"
                " was used during the initial run, unless you use the "
                "\" auto_pause_and_resume\" functionality. To turn this on, "
                " please go to your .spynnaker.cfg file and add "
                "[Mode] and use_auto_pause_and_resume = False")

        if application_graph_changed and self._has_ran:
            raise exceptions.ConfigurationException(
                "Changes to the application graph are not currently supported;"
                " please instead call p.reset(), p.end(), add changes and then"
                " call p.setup()")

        # if the application graph has changed and you've already ran, kill old
        # stuff running on machine
        if application_graph_changed and self._has_ran:
            self._txrx.stop_application(self._app_id)

        # get outputs
        required_outputs = self._create_pacman_executor_outputs(
            requires_reset=False,
            application_graph_changed=application_graph_changed)

        # algorithms listing
        algorithms, optional_algorithms = self._create_algorithm_list(
            config.get("Mode", "mode") == "Debug", application_graph_changed,
            executing_reset=False,
            using_auto_pause_and_resume=uses_auto_pause_and_resume)

        # xml paths to the algorithms metadata
        xml_paths = self._create_xml_paths()

        # run pacman executor
        execute_mapper = FrontEndCommonExecuteMapper()
        pacman_executor = execute_mapper.do_mapping(
            inputs=inputs, algorithms=algorithms,
            required_outputs=required_outputs, xml_paths=xml_paths,
            do_timings=config.getboolean("Reports", "outputTimesForSections"),
            algorithms_to_catch_prov_on_crash=
            self._algorithms_to_catch_prov_on_crash,
            prov_path=self._provenance_file_path,
            optional_algorithms=optional_algorithms)

        # sort out outputs data
        if application_graph_changed:
            self._update_data_structures_from_pacman_executor(
                pacman_executor, application_graph_changed,
                uses_auto_pause_and_resume)
        else:
            self._no_sync_changes = pacman_executor.get_item("NoSyncChanges")
            self._has_ran = pacman_executor.get_item("RanToken")

        # switch the reset last flag, as now the last thing to run is a run
        self._has_reset_last = False

        # gather provenance data from the executor itself if needed
        if config.get("Reports", "writeProvenanceData"):
            # get pacman provenance items
            prov_items = pacman_executor.get_provenance_data_items(
                pacman_executor.get_item("MemoryTransciever"))
            self._provenance_data_items.add_provenance_item_by_operation(
                "PACMAN", prov_items)
            # get spynnaker provenance
            prov_items = self.get_provenance_data_items(
                pacman_executor.get_item("MemoryTransciever"))
            self._provenance_data_items.add_provenance_item_by_operation(
                "FrontEndProvenanceData", prov_items)

    def reset(self):
        """ Code that puts the simulation back at time zero
        :return:
        """

        logger.info("Starting reset progress")

        inputs, application_graph_changed, using_auto_pause_and_resume = \
            self._create_pacman_executor_inputs(
                this_run_time=0, is_resetting=True)

        if self._has_ran and application_graph_changed:
            raise exceptions.ConfigurationException(
                "Resetting the simulation after changing the model"
                " is not supported")

        algorithms, optional_algorithms = self._create_algorithm_list(
            config.get("Mode", "mode") == "Debug", application_graph_changed,
            executing_reset=True,
            using_auto_pause_and_resume=using_auto_pause_and_resume)

        xml_paths = self._create_xml_paths()
        required_outputs = self._create_pacman_executor_outputs(
            requires_reset=True,
            application_graph_changed=application_graph_changed)

        # rewind the buffers from the buffer manager, to start at the beginning
        # of the simulation again and clear buffered out
        self._buffer_manager.reset()

        # reset the current count of how many milliseconds the application
        # has ran for over multiple calls to run
        self._current_run_ms = 0

        # change number of resets as loading the binary again resets the sync\
        # to 0
        self._no_sync_changes = 0

        # sets the has ran into false state, to pretend that its like it has
        # not ran
        self._has_ran = False

        # sets the reset last flag to true, so that when run occurs, the tools
        # know to update the vertices which need to know a reset has occurred
        self._has_reset_last = True

        # reset the n_machine_time_steps from each vertex
        for vertex in self.partitionable_graph.vertices:
            vertex.set_no_machine_time_steps(0)

        # execute reset functionality
        execute_mapper = FrontEndCommonExecuteMapper()
        execute_mapper.do_mapping(
            inputs, algorithms, optional_algorithms, required_outputs,
            xml_paths, config.getboolean("Reports", "outputTimesForSections"),
            self._algorithms_to_catch_prov_on_crash,
            prov_path=self._provenance_file_path)

        # if graph has changed kill all old objects as they will need to be
        # rebuilt at next run
        if application_graph_changed:
            self._placements = self._router_tables = self._routing_infos = \
                self._tags = self._graph_mapper = self._partitioned_graph = \
                self._database_interface = self._executable_targets = \
                self._placement_to_app_data_file_paths = \
                self._processor_to_app_data_base_address_mapper = None

    def _update_data_structures_from_pacman_executor(
            self, pacman_executor, application_graph_changed,
            uses_auto_pause_and_resume):
        """ Updates all the spinnaker local data structures that it needs from\
            the pacman executor
        :param pacman_executor: the pacman executor required to extract data\
                structures from.
        :return:
        """
        if application_graph_changed:
            if not config.getboolean("Machine", "virtual_board"):
                self._txrx = pacman_executor.get_item("MemoryTransciever")
                self._executable_targets = \
                    pacman_executor.get_item("ExecutableTargets")
                self._buffer_manager = pacman_executor.get_item("BufferManager")
                self._processor_to_app_data_base_address_mapper = \
                    pacman_executor.get_item("ProcessorToAppDataBaseAddress")
                self._placement_to_app_data_file_paths = \
                    pacman_executor.get_item("PlacementToAppDataFilePaths")

            self._placements = pacman_executor.get_item("MemoryPlacements")
            self._router_tables = \
                pacman_executor.get_item("MemoryRoutingTables")
            self._routing_infos = \
                pacman_executor.get_item("MemoryRoutingInfos")
            self._tags = pacman_executor.get_item("MemoryTags")
            self._graph_mapper = pacman_executor.get_item("MemoryGraphMapper")
            self._partitioned_graph = \
                pacman_executor.get_item("MemoryPartitionedGraph")
            self._machine = pacman_executor.get_item("MemoryMachine")
            self._database_interface = \
                pacman_executor.get_item("DatabaseInterface")
            self._database_file_path = \
                pacman_executor.get_item("DatabaseFilePath")
            self._dsg_targets = \
                pacman_executor.get_item("DataSpecificationTargets")

        if uses_auto_pause_and_resume:
            self._steps = pacman_executor.get_item("Steps")

        # update stuff that always needed updating
        self._no_sync_changes = pacman_executor.get_item("NoSyncChanges")
        self._has_ran = pacman_executor.get_item("RanToken")
        if uses_auto_pause_and_resume:
            self._current_run_ms = \
                pacman_executor.get_item("TotalAccumulativeRunTime")
        else:
            self._current_run_ms += pacman_executor.get_item("RunTime")

    def get_provenance_data_items(self, transceiver, placement=None):
        """
        @implements pacman.interface.abstract_provides_provenance_data.AbstractProvidesProvenanceData.get_provenance_data_items
        :return:
        """
        prov_items = list()
        prov_items.append(ProvenanceDataItem(
            name="ip_address",
            item=str(self._hostname)))
        prov_items.append(ProvenanceDataItem(
            name="software_version",
            item="{}:{}:{}:{}".format(
                self._version.__version__, self._version.__version_name__,
                self._version.__version_year__,
                self._version.__version_month__)))
        prov_items.append(ProvenanceDataItem(
            name="machine_time_step",
            item=str(self._machine_time_step)))
        prov_items.append(ProvenanceDataItem(
            name="time_scale_factor",
            item=str(self._time_scale_factor)))
        prov_items.append(ProvenanceDataItem(
            name="total_runtime",
            item=str(self._current_run_ms)))
        return prov_items

    def _create_xml_paths(self):

        # add the extra xml files from the config file
        xml_paths = config.get("Mapping", "extra_xmls_paths")
        if xml_paths == "None":
            xml_paths = list()
        else:
            xml_paths = xml_paths.split(",")

        xml_paths.extend(self._extra_algorithm_xml_paths)

        xml_paths.append(os.path.join(os.path.dirname(
            pacman_algorithm_reports.__file__), "reports_metadata.xml"))
        return xml_paths

    @abstractmethod
    def _create_algorithm_list(
            self, in_debug_mode, application_graph_changed, executing_reset,
            using_auto_pause_and_resume):
        """
        method required to be implimented by front ends. supported by the
        private method _create_all_flows_algorithm_common
        :param in_debug_mode: if the code should run in debug mode
        :param application_graph_changed: has the application graph changed
        :param executing_reset: are we exeucting a reset function
        :param using_auto_pause_and_resume: are we using auto pause and
        resume functionality
        :return: a iterable of algorithm names
        :rtype: iterable of str
        """

    def _create_all_flows_algorithm_common(
            self, in_debug_mode, application_graph_changed, executing_reset,
            using_auto_pause_and_resume, mapping_algorithms):
        """
        creates the list of algorithms to use within the system
        :param in_debug_mode: if the tools should be operating in debug mode
        :param application_graph_changed: has the graph changed since last run
        :param executing_reset: are we executing a reset function
        :param using_auto_pause_and_resume: check if the system is to use
        auto pause and resume functionality
        :param mapping_algorithms: list of algorithms to use during mapping
        process
        :return: list of algorithms to use and a list of optional
        algorithms to use
        """
        algorithms = list()
        optional_algorithms = list()

        # if you've not ran before, add the buffer manager
        using_virtual_board = config.getboolean("Machine", "virtual_board")
        if application_graph_changed and not using_virtual_board:
            if not using_auto_pause_and_resume:
                optional_algorithms.append("FrontEndCommonBufferManagerCreator")

        # if you're needing a reset, you need to clean the binaries
        # (unless you've not ran yet)
        if executing_reset and self._has_ran:
            # kill binaries
            # TODO: when SARK 1.34 appears, this only needs to send a signal
            algorithms.append("FrontEndCommonApplicationFinisher")

        # if the allocation graph has changed, need to go through mapping
        if application_graph_changed and not executing_reset:

            # if the system has ran before, kill the apps and run mapping
            # add debug algorithms if needed
            if in_debug_mode:
                algorithms.append("ValidRoutesChecker")

            # add mapping algorithms to the pile
            algorithms.extend(mapping_algorithms)

            # if using virtual machine, add to list of algorithms the virtual
            # machine generator, otherwise add the standard machine generator
            if using_virtual_board:
                algorithms.append("FrontEndCommonVirtualMachineInterfacer")
            else:
                # protect against the situation where the system has already
                # got a transceiver (overriding does not lose sockets)
                if self._txrx is not None:
                    self._txrx.close()
                    self._txrx = None

                if self._exec_dse_on_host:
                    # The following lines are not split to avoid error
                    # in future search
                    algorithms.append(
                        "FrontEndCommonPartitionableGraphHostExecuteDataSpecification")  # @IgnorePep8
                else:
                    algorithms.append(
                        "FrontEndCommonPartitionableGraphMachineExecuteDataSpecification")  # @IgnorePep8


                algorithms.append("FrontEndCommonMachineInterfacer")
                algorithms.append("FrontEndCommonNotificationProtocol")
                optional_algorithms.append("FrontEndCommonRoutingTableLoader")
                optional_algorithms.append("FrontEndCommonTagsLoader")

                # add algorithms that the auto supplies if not using it
                if not using_auto_pause_and_resume:
                    optional_algorithms.append(
                        "FrontEndCommonLoadExecutableImages")
                    algorithms.append("FrontEndCommonApplicationRunner")
                    optional_algorithms.append(
                        "FrontEndCommonApplicationDataLoader")
                    algorithms.append("FrontEndCommonLoadExecutableImages")

                    if len(self._partitionable_graph.vertices) != 0:
                        algorithms.append(
                            "FrontEndCommonPartitionableGraphHostExecuteDataSpecification")  # @IgnorePep8
                        algorithms.append(
                            "FrontEndCommonPartitionableGraphDataSpecificationWriter")  # @IgnorePep8
                    elif len(self._partitioned_graph.subvertices) != 0:
                        algorithms.append(
                            "FrontEndCommonPartitionedGraphDataSpecificationWriter")  # @IgnorePep8
                        algorithms.append(
                            "FrontEndCommonPartitionedGraphHostBasedDataSpecificationExeuctor")  # @IgnorePep8

                algorithms.append("FrontEndCommonMachineInterfacer")
                algorithms.append("FrontEndCommonApplicationRunner")
                algorithms.append("FrontEndCommonNotificationProtocol")
                algorithms.append("FrontEndCommomLoadExecutableImages")
                algorithms.append("FrontEndCommonRoutingTableLoader")
                algorithms.append("FrontEndCommonTagsLoader")
                algorithms.append("FrontEndCommomPartitionableGraphData"
                                  "SpecificationWriter")

                # if the end user wants reload script, add the reload script
                # creator to the list (reload script currently only supported
                # for the original run)
                write_reload = config.getboolean("Reports", "writeReloadSteps")

                # if reload and auto pause and resume are on, raise exception
                if write_reload and using_auto_pause_and_resume:
                    raise exceptions.ConfigurationException(
                        "You cannot use auto pause and resume with a "
                        "reload script. This is due to reload not being able to"
                        "extract data from the machine. Please fix and try "
                        "again")

                # if first run, create reload
                if not self._has_ran and write_reload:
                    algorithms.append("FrontEndCommonReloadScriptCreator")

                # if ran before, warn that reload is only available for
                # first run
                elif self.has_ran and write_reload:
                    logger.warn(
                        "The reload script cannot handle multi-runs, nor can"
                        "it handle resets, therefore it will only contain the "
                        "initial run")

            if (config.getboolean("Reports", "writeMemoryMapReport")
                    and not using_virtual_board):
                if self._exec_dse_on_host:
                    algorithms.append("FrontEndCommonMemoryMapOnHostReport")
                else:
                    algorithms.append("FrontEndCommonMemoryMapOnChipReport")

            if config.getboolean("Reports", "writeNetworkSpecificationReport"):
                algorithms.append(
                    "FrontEndCommonNetworkSpecificationPartitionableReport")

            # define mapping between output types and reports
            if self._reports_states is not None \
                    and self._reports_states.tag_allocation_report:
                algorithms.append("TagReport")
            if self._reports_states is not None \
                    and self._reports_states.routing_info_report:
                algorithms.append("routingInfoReports")
                algorithms.append("unCompressedRoutingTableReports")
                algorithms.append("compressedRoutingTableReports")
                algorithms.append("comparisonOfRoutingTablesReport")
            if self._reports_states is not None \
                    and self._reports_states.router_report:
                algorithms.append("RouterReports")
            if self._reports_states is not None \
                    and self._reports_states.partitioner_report:
                algorithms.append("PartitionerReport")
            if (self._reports_states is not None and
                    self._reports_states.
                    placer_report_with_partitionable_graph):
                algorithms.append("PlacerReportWithPartitionableGraph")
            if (self._reports_states is not None and
                    self._reports_states.
                    placer_report_without_partitionable_graph):
                algorithms.append("PlacerReportWithoutPartitionableGraph")

        elif not executing_reset:
            # add function for extracting all the recorded data from
            # recorded populations
            if self._has_ran:
                # add functions for updating the models
                algorithms.append("FrontEndCommonRuntimeUpdater")
            if not self._has_ran:
                optional_algorithms.append(
                    "FrontEndCommonApplicationDataLoader")
                algorithms.append("FrontEndCommonLoadExecutableImages")

                if self._exec_dse_on_host:
                    # The following lines are not split to avoid error
                    # in future search
                    algorithms.append(
                        "FrontEndCommonPartitionableGraphApplicationDataLoader")  # @IgnorePep8
                else:
                    algorithms.append(
                        "FrontEndCommonPartitionableGraphMachineExecuteDataSpecification")  # @IgnorePep8

            # add default algorithms
            algorithms.append("FrontEndCommonNotificationProtocol")

            # add functions for setting off the models again
            if using_auto_pause_and_resume:
                algorithms.append("FrontEndCommonAutoPauseAndResumeExecutor")
            else:
                algorithms.append("FrontEndCommonApplicationRunner")

        return algorithms, optional_algorithms

    def _create_pacman_executor_outputs(
            self, requires_reset, application_graph_changed):

        # explicitly define what outputs spynnaker expects
        required_outputs = list()
        if config.getboolean("Machine", "virtual_board"):
            if application_graph_changed:
                required_outputs.extend([
                    "MemoryPlacements", "MemoryRoutingTables",
                    "MemoryRoutingInfos", "MemoryTags",
                    "MemoryPartitionedGraph", "MemoryGraphMapper"])
        else:
            if not requires_reset:
                required_outputs.append("RanToken")

        # if front end wants reload script, add requires reload token
        if (config.getboolean("Reports", "writeReloadSteps") and
                not self._has_ran and application_graph_changed and
                not config.getboolean("Machine", "virtual_board")):
            required_outputs.append("ReloadToken")
        return required_outputs

    def _create_pacman_executor_inputs(
            self, this_run_time, is_resetting=False):

        application_graph_changed, self._no_sync_changes, \
            no_machine_time_steps, json_folder, width, height, \
            number_of_boards, scamp_socket_addresses, boot_port_num, \
            using_auto_pause_and_resume, max_sdram_size = \
            self._deduce_standard_input_params(is_resetting, this_run_time)

        inputs = list()
        inputs = self._add_standard_basic_inputs(
            inputs, no_machine_time_steps, is_resetting, max_sdram_size,
            this_run_time)

        # if using auto_pause and resume, add basic pause and resume inputs
        if using_auto_pause_and_resume:
            inputs = self._add_auto_pause_and_resume_inputs(
                inputs, application_graph_changed, is_resetting)

        # FrontEndCommonApplicationDataLoader after a reset and no changes
        if not self._has_ran and not application_graph_changed:
            inputs = self._add_resetted_last_and_no_change_inputs(inputs)

        # support resetting when there's changes in the application graph
        # (only need to exit)
        if application_graph_changed and is_resetting:
            inputs = self._add_inputs_for_reset_with_changes(inputs)

        # mapping required
        elif application_graph_changed and not is_resetting:
            inputs = self._add_mapping_inputs(
                inputs, width, height, scamp_socket_addresses, boot_port_num,
                json_folder, number_of_boards)

            # if already ran, this is a remapping, thus needs to warn end user
            if self._has_ran:
                logger.warn(
                    "The network has changed, and therefore mapping will be"
                    " done again.  Any recorded data will be erased.")
        #
        else:
            inputs = self._add_extra_run_inputs(inputs)

        return inputs, application_graph_changed, using_auto_pause_and_resume

    def _deduce_standard_input_params(self, is_resetting, this_run_time):
        application_graph_changed = \
            self._detect_if_graph_has_changed(not is_resetting)

        # all modes need the NoSyncChanges
        if application_graph_changed:
            self._no_sync_changes = 0

        # all modes need the runtime in machine time steps
        # (partitioner and rerun)
        no_machine_time_steps = \
            int(((this_run_time - self._current_run_ms) * 1000.0)
                / self._machine_time_step)

        # make a folder for the json files to be stored in
        json_folder = os.path.join(
            self._report_default_directory, "json_files")
        if not os.path.exists(json_folder):
            os.mkdir(json_folder)

        # translate config "None" to None
        width = config.get("Machine", "width")
        height = config.get("Machine", "height")
        if width == "None":
            width = None
        else:
            width = int(width)
        if height == "None":
            height = None
        else:
            height = int(height)

        number_of_boards = config.get("Machine", "number_of_boards")
        if number_of_boards == "None":
            number_of_boards = None

        scamp_socket_addresses = config.get("Machine",
                                            "scamp_connections_data")
        if scamp_socket_addresses == "None":
            scamp_socket_addresses = None

        boot_port_num = config.get("Machine", "boot_connection_port_num")
        if boot_port_num == "None":
            boot_port_num = None
        else:
            boot_port_num = int(boot_port_num)

        # if your using the auto pause and resume, then add the inputs needed
        # for this functionality.
        using_auto_pause_and_resume = \
            config.getboolean("Mode", "use_auto_pause_and_resume")

        # used for debug purposes to fix max size of sdram each chip has
        max_sdram_size = config.get("Machine", "max_sdram_allowed_per_chip")
        if max_sdram_size == "None":
            max_sdram_size = None
        else:
            max_sdram_size = int(max_sdram_size)

        return \
            application_graph_changed, self._no_sync_changes, \
            no_machine_time_steps, json_folder, width, height, \
            number_of_boards, scamp_socket_addresses, boot_port_num, \
            using_auto_pause_and_resume, max_sdram_size

    def _add_extra_run_inputs(self, inputs):
        # mapping does not need to be executed, therefore add
        # the data elements needed for the application runner and
        # runtime re-setter
        inputs.append({
            "type": "BufferManager",
            "value": self._buffer_manager})
        inputs.append({
            'type': "DatabaseWaitOnConfirmationFlag",
            'value': config.getboolean("Database", "wait_on_confirmation")})
        inputs.append({
            'type': "SendStartNotifications",
            'value': config.getboolean("Database", "send_start_notification")})
        inputs.append({
            'type': "DatabaseInterface",
            'value': self._database_interface})
        inputs.append({
            "type": "DatabaseSocketAddresses",
            'value': self._database_socket_addresses})
        inputs.append({
            'type': "DatabaseFilePath",
            'value': self._database_file_path})
        inputs.append({
            'type': "ExecutableTargets",
            'value': self._executable_targets})
        inputs.append({
            'type': "APPID",
            'value': self._app_id})
        inputs.append({
            "type": "MemoryTransciever",
            'value': self._txrx})
        inputs.append({
            'type': "TimeScaleFactor",
            'value': self._time_scale_factor})
        inputs.append({
            'type': "LoadedReverseIPTagsToken",
            'value': True})
        inputs.append({
            'type': "LoadedIPTagsToken",
            'value': True})
        inputs.append({
            'type': "LoadedRoutingTablesToken",
            'value': True})
        if not self._has_reset_last:
            inputs.append({
                'type': "LoadBinariesToken",
                'value': True})
        inputs.append({
            'type': "LoadedApplicationDataToken",
            'value': True})
        inputs.append({
            'type': "MemoryPlacements",
            'value': self._placements})
        inputs.append({
            'type': "MemoryGraphMapper",
            'value': self._graph_mapper})
        inputs.append({
            'type': "MemoryPartitionableGraph",
            'value': self._partitionable_graph})
        inputs.append({
            'type': "MemoryExtendedMachine",
            'value': self._machine})
        inputs.append({
            'type': "MemoryRoutingTables",
            'value': self._router_tables})
        inputs.append({
            'type': "RanToken",
            'value': self._has_ran})
        return inputs

    def _add_mapping_inputs(
            self, inputs, width, height, scamp_socket_addresses, boot_port_num,
            json_folder, number_of_boards):

        # basic input stuff
        inputs.append({
            'type': "MemoryPartitionableGraph",
            'value': self._partitionable_graph})
        inputs.append({
            'type': 'ReportFolder',
            'value': self._report_default_directory})
        inputs.append({
            'type': 'IPAddress',
            'value': self._hostname})
        inputs.append({
            'type': "BMPDetails",
            'value': config.get("Machine", "bmp_names")})
        inputs.append({
            'type': "DownedChipsDetails",
            'value': config.get("Machine", "down_chips")})
        inputs.append({
            'type': "DownedCoresDetails",
            'value': config.get("Machine", "down_cores")})
        inputs.append({
            'type': "BoardVersion",
            'value': config.getint("Machine", "version")})
        inputs.append({
            'type': "NumberOfBoards",
            'value': number_of_boards})
        inputs.append({
            'type': "MachineWidth",
            'value': width})
        inputs.append({
            'type': "MachineHeight",
            'value': height})
        inputs.append({
            'type': "AutoDetectBMPFlag",
            'value': config.getboolean("Machine", "auto_detect_bmp")})
        inputs.append({
            'type': "EnableReinjectionFlag",
            'value': config.getboolean("Machine", "enable_reinjection")})
        inputs.append({
            'type': "ScampConnectionData",
            'value': scamp_socket_addresses})
        inputs.append({
            'type': "BootPortNum",
            'value': boot_port_num})
        inputs.append({
            'type': "APPID",
            'value': self._app_id})
        inputs.append({
            'type': "DSEAPPID",
            'value': self._dse_app_id})
        inputs.append({
            'type': "TimeScaleFactor",
            'value': self._time_scale_factor})
        inputs.append({
            'type': "DatabaseSocketAddresses",
            'value': self._database_socket_addresses})
        inputs.append({
            'type': "DatabaseWaitOnConfirmationFlag",
            'value': config.getboolean("Database", "wait_on_confirmation")})
        inputs.append({
            'type': "WriteTextSpecsFlag",
            'value': config.getboolean("Reports", "writeTextSpecs")})
        inputs.append({
            'type': "ExecutableFinder",
            'value': executable_finder})
        inputs.append({
            'type': "MachineHasWrapAroundsFlag",
            'value': config.getboolean("Machine", "requires_wrap_arounds")})
        inputs.append({
            'type': "ReportStates",
            'value': self._reports_states})
        inputs.append({
            'type': "UserCreateDatabaseFlag",
            'value': config.get("Database", "create_database")})
        inputs.append({
            'type': "ExecuteMapping",
            'value': config.getboolean(
                "Database", "create_routing_info_to_neuron_id_mapping")})
        inputs.append({
            'type': "SendStartNotifications",
            'value': config.getboolean("Database", "send_start_notification")})

        # add paths for each file based version
        inputs.append({
            'type': "FileCoreAllocationsFilePath",
            'value': os.path.join(json_folder, "core_allocations.json")})
        inputs.append({
            'type': "FileSDRAMAllocationsFilePath",
            'value': os.path.join(json_folder, "sdram_allocations.json")})
        inputs.append({
            'type': "FileMachineFilePath",
            'value': os.path.join(json_folder, "machine.json")})
        inputs.append({
            'type': "FilePartitionedGraphFilePath",
            'value': os.path.join(json_folder, "partitioned_graph.json")})
        inputs.append({
            'type': "FilePlacementFilePath",
            'value': os.path.join(json_folder, "placements.json")})
        inputs.append({
            'type': "FileRoutingPathsFilePath",
            'value': os.path.join(json_folder, "routing_paths.json")})
        inputs.append({'type': "FileConstraintsFilePath",
                       'value': os.path.join(json_folder, "constraints.json")})
        return inputs

    def _add_inputs_for_reset_with_changes(self, inputs):
        inputs.append({
            "type": "MemoryTransciever",
            'value': self._txrx})
        inputs.append({
            'type': "ExecutableTargets",
            'value': self._executable_targets})
        inputs.append({
            'type': "MemoryPlacements",
            'value': self._placements})
        inputs.append({
            'type': "MemoryGraphMapper",
            'value': self._graph_mapper})
        inputs.append({
            'type': "APPID",
            'value': self._app_id})
        inputs.append({
            'type': "RanToken",
            'value': self._has_ran})
        return inputs

    def _add_standard_basic_inputs(
            self, inputs, no_machine_time_steps, is_resetting, max_sdram_size,
            this_run_time):

        # support resetting the machine during start up
        reset_machine_on_startup = \
            config.getboolean("Machine", "reset_machine_on_startup")
        needs_to_reset_machine = \
            (reset_machine_on_startup and not self._has_ran
             and not is_resetting)

        inputs.append({
            'type': 'TimeThreshold',
            'value': config.getint("Machine", "time_to_wait_till_error")})
        inputs.append({
            'type': "RunTime",
            'value': this_run_time})
        inputs.append({
            'type': "TotalAccumulativeRunTime",
            'value': self._current_run_ms})
        inputs.append({
            'type': "UseAutoPauseAndResume",
            'value': True})
        inputs.append({
            'type': "MaxSDRAMSize",
            'value': max_sdram_size})
        inputs.append({
            'type': "NoSyncChanges",
            'value': self._no_sync_changes})
        inputs.append({
            'type': "RunTimeMachineTimeSteps",
            'value': no_machine_time_steps})
        inputs.append({
            'type': "MachineTimeStep",
            'value': self._machine_time_step})
        inputs.append({
            "type": "ResetMachineOnStartupFlag",
            'value': needs_to_reset_machine})
        # stuff most versions need
        inputs.append({
            'type': "WriteCheckerFlag",
            'value': config.getboolean("Mode", "verify_writes")})
        inputs.append({
            'type': "ReportStates",
            'value': self._reports_states})
        inputs.append({
            'type': "ApplicationDataFolder",
            'value': self._app_data_runtime_folder})

        return inputs

    def _add_resetted_last_and_no_change_inputs(self, inputs):
        inputs.append(({
            'type': "ProcessorToAppDataBaseAddress",
            "value": self._processor_to_app_data_base_address_mapper}))
        inputs.append({
            "type": "PlacementToAppDataFilePaths",
            'value': self._placement_to_app_data_file_paths})
        inputs.append({
            'type': "WriteCheckerFlag",
            'value': config.getboolean("Mode", "verify_writes")})
        return inputs

    def _add_auto_pause_and_resume_inputs(
            self, inputs, application_graph_changed, is_resetting):
        # due to the mismatch between dsg's and dse's in different front
        # end, the inputs not given to the multiple pause and resume but
        # which are needed for dsg/dse need to be put in the extra inputs

        extra_xmls = list()
        extra_xmls.extend(self._extra_algorithm_xml_paths)

        extra_inputs = list()
        extra_inputs.append({
            'type': 'ExecutableFinder',
            'value': executable_finder})
        extra_inputs.append({
            'type': 'IPAddress',
            'value': self._hostname})
        extra_inputs.append({
            'type': 'ReportFolder',
            'value': self._report_default_directory})
        extra_inputs.append({
            'type': 'WriteTextSpecsFlag',
            'value': config.getboolean("Reports", "writeTextSpecs")})
        extra_inputs.append({
            'type': 'ApplicationDataFolder',
            'value': self._app_data_runtime_folder})
        extra_inputs.append({
            'type': "TotalAccumulativeRunTime",
            'value': self._current_run_ms})
        extra_inputs.append({
            'type': "MachineTimeStep",
            'value': self._machine_time_step})
        if not self._exec_dse_on_host:
            extra_inputs.append({
                'type': "DSEAPPID",
                'value': self._dse_app_id})

        # standard inputs
        inputs.append({
            'type': "ExtraAlgorithms",
            'value': self._extra_algorithms_for_auto_pause_and_resume})
        inputs.append({
            'type': "ExtraInputs",
            'value': extra_inputs})
        inputs.append({
            'type': "ExtraXMLS",
            'value': extra_xmls})
        inputs.append({
            'type': "DSGeneratorAlgorithm",
            'value': "FrontEndCommonPartitionableGraphDataSpecificationWriter"})
        if self._exec_dse_on_host:
            inputs.append({
                'type': "DSExecutorAlgorithm",
                'value':
                    "FrontEndCommonPartitionableGraphHostExecuteDataSpecification"})  # @IgnorePep8
        else:
            inputs.append({
                'type': "DSExecutorAlgorithm",
                'value':
                    "FrontEndCommonPartitionableGraphMachineExecuteDataSpecification"})  # @IgnorePep8
        inputs.append({
            'type': "HasRanBefore",
            'value': self._has_ran})
        inputs.append({
            'type': "ApplicationGraphChanged",
            'value': application_graph_changed})
        inputs.append({
            'type': "HasResetBefore",
            'value': self._has_reset_last})
        inputs.append({
            'type': "Steps",
            'value': self._steps})

        # add extra needed by auto_pause and resume if reset has occurred
        if not application_graph_changed and not is_resetting:
            inputs.append({
                'type': "MemoryRoutingInfos",
                'value': self._routing_infos})
            inputs.append({
                'type': "MemoryPartitionedGraph",
                'value': self._partitioned_graph})
            inputs.append({
                'type': "MemoryTags",
                'value': self._tags})
            extra_inputs.append({
                'type': "LoadedApplicationDataToken",
                'value': True})
            extra_inputs.append({
                'type': "ExecutableTargets",
                'value': self._executable_targets})
            extra_inputs.append({
                'type': "DataSpecificationTargets",
                'value': self._dsg_targets})
            extra_inputs.append({
                'type': "ProcessorToAppDataBaseAddress",
                'value': self._processor_to_app_data_base_address_mapper})
            extra_inputs.append({
                'type': "PlacementToAppDataFilePaths",
                'value': self._placement_to_app_data_file_paths})
            extra_inputs.append({
                'type': "LoadBinariesToken",
                'value': True})

        # multi run mode
        if not application_graph_changed and self._has_ran:
            extra_inputs.append({
                'type': "LoadBinariesToken",
                'value': True})
            extra_inputs.append({
                'type': "RanToken",
                'value': True})
        if self._buffer_manager is not None:
            extra_inputs.append({
                'type': "BufferManager",
                'value': self._buffer_manager})

        return inputs

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

        # if operating in debug mode, extract io buffers from all machine
        self._run_debug_iobuf_extraction_for_exit(
            config.get("Mode", "mode") == "Debug")

        # if not a virtual machine, then shut down stuff on the board
        if not config.getboolean("Machine", "virtual_board"):

            if turn_off_machine is None:
                turn_off_machine = \
                    config.getboolean("Machine", "turn_off_machine")

            if clear_routing_tables is None:
                clear_routing_tables = config.getboolean(
                    "Machine", "clear_routing_tables")

            if clear_tags is None:
                clear_tags = config.getboolean("Machine", "clear_tags")

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
                    if not self._machine.get_chip_at(router_table.x,
                                                     router_table.y).virtual:
                        self._txrx.clear_multicast_routes(router_table.x,
                                                          router_table.y)

            # clear values
            self._no_sync_changes = 0

            # app stop command
            if config.getboolean("Machine", "use_app_stop"):
                self._txrx.stop_application(self._app_id)

            if self._create_database:
                self._database_interface.stop()

            self._buffer_manager.stop()

            # stop the transceiver
            if turn_off_machine:
                logger.info("Turning off machine")
            self._txrx.close(power_off_machine=turn_off_machine)

    def _run_debug_iobuf_extraction_for_exit(self, in_debug_mode):

        pacman_inputs = list()
        pacman_inputs.append({
            'type': "MemoryTransciever",
            'value': self._txrx})
        pacman_inputs.append({
            'type': "RanToken",
            'value': True})
        pacman_inputs.append({
            'type': "MemoryPlacements",
            'value': self._placements})
        pacman_inputs.append({
            'type': "ProvenanceFilePath",
            'value': self._provenance_file_path})
        pacman_inputs.append({
            'type': "ProvenanceItems",
            'value': self._provenance_data_items})
        pacman_inputs.append({
            'type': "MemoryRoutingTables",
            'value': self._router_tables})
        pacman_inputs.append({
            'type': "MemoryExtendedMachine",
            'value': self._machine})
        pacman_inputs.append({
            'type': "MemoryMachine",
            'value': self._machine})
        pacman_inputs.append({
            'type': 'FileMachineFilePath',
            'value': os.path.join(self._provenance_file_path,
                                  "Machine.json")})

        pacman_outputs = list()
        if in_debug_mode:
            pacman_outputs.append("FileMachine")
            pacman_outputs.append("ErrorMessages")
            pacman_outputs.append("IOBuffers")
        pacman_outputs.append("ProvenanceItems")

        pacman_algorithms = list()
        pacman_algorithms.append("FrontEndCommonProvenanceGatherer")
        pacman_algorithms.append("FrontEndCommonProvenanceXMLWriter")
        if in_debug_mode:
            pacman_algorithms.append("FrontEndCommonIOBufExtractor")
            pacman_algorithms.append("FrontEndCommonWarningGenerator")
            pacman_algorithms.append("FrontEndCommonMessagePrinter")
        pacman_xmls = list()
        pacman_xmls.append(
            os.path.join(os.path.dirname(interface_functions.__file__),
                         "front_end_common_interface_functions.xml"))
        pacman_executor = PACMANAlgorithmExecutor(
            algorithms=pacman_algorithms, inputs=pacman_inputs,
            xml_paths=pacman_xmls, required_outputs=pacman_outputs,
            optional_algorithms=list())
        pacman_executor.execute_mapping()

    def add_partitionable_vertex(self, vertex_to_add):
        """

        :param vertex_to_add: the partitionable vertex to add to the graph
        :return: None
        :raises: ConfigurationException when both graphs contain vertices
        """
        if len(self._partitioned_graph.subvertices) > 0:
            raise exceptions.ConfigurationException(
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
            raise exceptions.ConfigurationException(
                "The partitionable graph has already got some vertices, and "
                "therefore the application cannot be executed correctly due "
                "to not knowing how these two graphs interact with each "
                "other. Please rectify and try again")

        if self._partitioned_graph is None:
            self._partitioned_graph = PartitionedGraph(
                label="partitioned_graph for application id {}"
                .format(self._app_id))
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

    def _add_socket_address(self, socket_address):
        """

        :param socket_address:
        :return:
        """
        self._database_socket_addresses.add(socket_address)

    @property
    def app_id(self):
        """

        :return:
        """
        return self._app_id

    @property
    def using_auto_pause_and_resume(self):
        """

        :return:
        """
        return self._using_auto_pause_and_resume

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
    def writing_reload_script(self):
        """
        returns if the system is to use auto_pause and resume
        :return:
        """
        return config.getboolean("Reports", "writeReloadSteps")

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
    def routing_infos(self):
        """

        :return:
        """
        return self._routing_infos

    @property
    def buffer_manager(self):
        """
        returns the buffer manager used for extracting/injecting data in
        buffer form
        :return:
        """
        return self._buffer_manager

    @property
    def none_labelled_vertex_count(self):
        """
        the number of times vertices have not been labelled.
        :return: the number of times the vertices have not been labelled
        """
        return self._non_labelled_vertex_count

    def increment_none_labelled_vertex_count(self):
        """
        increments the number of new vertices which havent been labelled.
        :return: None
        """
        self._non_labelled_vertex_count += 1

    @property
    def none_labelled_edge_count(self):
        """
        the number of times vertices have not been labelled.
        :return: the number of times the vertices have not been labelled
        """
        return self._none_labelled_edge_count

    def increment_none_labelled_edge_count(self):
        """
        increments the number of new edges which havent been labelled.
        :return: None
        """
        self._non_labelled_edge_count += 1

    def set_app_id(self, value):
        """

        :param value:
        :return:
        """
        self._app_id = value

    def get_current_time(self):
        """

        :return:
        """
        if self._has_ran:
            return float(self._current_run_ms)
        return 0.0

    def __repr__(self):
        return "general front end instance for machine {}"\
            .format(self._hostname)
