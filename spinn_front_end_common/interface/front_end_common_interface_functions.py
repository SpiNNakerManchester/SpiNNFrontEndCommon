"""
interface for communciating with spinnaker machine easily.
"""
from data_specification.data_specification_executor import \
    DataSpecificationExecutor
from data_specification.file_data_writer import FileDataWriter
from data_specification.file_data_reader import FileDataReader

# pacman imports
from pacman.utilities.progress_bar import ProgressBar

# spinnmachine imports
from spinn_machine.sdram import SDRAM
from spinn_machine.virutal_machine import VirtualMachine

# spinnman imports
from spinnman.messages.scp.scp_signal import SCPSignal
from spinnman.model.cpu_state import CPUState
from spinnman.transceiver import create_transceiver_from_hostname
from spinnman.data.file_data_reader import FileDataReader \
    as SpinnmanFileDataReader
from spinnman.model.core_subsets import CoreSubsets
from spinnman.model.core_subset import CoreSubset

# front end common imports
from spinn_front_end_common.abstract_models.abstract_data_specable_vertex \
    import AbstractDataSpecableVertex
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities import reports

# general imports
import time
import os
import logging
import traceback

logger = logging.getLogger(__name__)


class FrontEndCommonInterfaceFunctions(object):
    """
    the front end common interface which supports functions such as :
    setting up the python spinnMachine
    writing data to spinnaker machine
    loading tags
    etc
    """

    def __init__(self, reports_states, report_default_directory):
        self._reports_states = reports_states
        self._report_default_directory = report_default_directory
        self._machine = None

    def _setup_interfaces(
            self, hostname, requires_virtual_board, downed_chips, downed_cores,
            virtual_x_dimension, virtual_y_dimension, requires_wrap_around,
            machine_version):
        """Set up the interfaces for communicating with the SpiNNaker board
        """

        if not requires_virtual_board:
            ignored_chips = None
            ignored_cores = None
            if downed_chips is not None and downed_chips != "None":
                ignored_chips = CoreSubsets()
                for downed_chip in downed_chips.split(":"):
                    x, y = downed_chip.split(",")
                    ignored_chips.add_core_subset(CoreSubset(int(x), int(y),
                                                             []))
            if downed_cores is not None and downed_cores != "None":
                ignored_cores = CoreSubsets()
                for downed_core in downed_cores.split(":"):
                    x, y, processor_id = downed_core.split(",")
                    ignored_cores.add_processor(int(x), int(y),
                                                int(processor_id))

            self._txrx = create_transceiver_from_hostname(
                hostname=hostname,
                discover=False,
                ignore_chips=ignored_chips,
                ignore_cores=ignored_cores)

            # do autoboot if possible
            if machine_version is None:
                raise exceptions.ConfigurationException(
                    "Please set a machine version number in the configuration "
                    "file (spynnaker.cfg or pacman.cfg)")
            self._txrx.ensure_board_is_ready(int(machine_version))
            self._txrx.discover_scamp_connections()
            self._machine = self._txrx.get_machine_details()
        else:
            self._machine = VirtualMachine(
                x_dimension=virtual_x_dimension,
                y_dimension=virtual_y_dimension,
                with_wrap_arounds=requires_wrap_around)

    def _load_tags(self, tags):
        """ loads all the tags onto all the boards
        """
        for ip_tag in tags.ip_tags:
            self._txrx.set_ip_tag(ip_tag)
        for reverse_ip_tag in tags.reverse_ip_tags:
            self._txrx.set_reverse_ip_tag(reverse_ip_tag)

    def _retieve_provance_data_from_machine(
            self, executable_targets, routing_tables, machine):

        # create writer to a report in reports
        reports.generate_provance_routings(routing_tables, machine, self._txrx,
                                           self._report_default_directory)

    def execute_data_specification_execution(
            self, host_based_execution, hostname, placements, graph_mapper,
            write_text_specs, runtime_application_data_folder):
        """

        :param host_based_execution:
        :param hostname:
        :param placements:
        :param graph_mapper:
        :param write_text_specs:
        :param runtime_application_data_folder:
        :return:
        """
        if host_based_execution:
            return self.host_based_data_specification_execution(
                hostname, placements, graph_mapper, write_text_specs,
                runtime_application_data_folder)
        else:
            return self._chip_based_data_specification_execution(hostname)

    def _chip_based_data_specification_execution(self, hostname):
        raise NotImplementedError

    def host_based_data_specification_execution(
            self, hostname, placements, graph_mapper, write_text_specs,
            application_data_runtime_folder):
        """

        :param hostname:
        :param placements:
        :param graph_mapper:
        :param write_text_specs:
        :param application_data_runtime_folder:
        :return:
        """
        space_based_memory_tracker = dict()
        processor_to_app_data_base_address = dict()

        # create a progress bar for end users
        progress_bar = ProgressBar(len(list(placements.placements)),
                                   "on executing data specifications on the "
                                   "host machine")

        for placement in placements.placements:
            associated_vertex = graph_mapper.get_vertex_from_subvertex(
                placement.subvertex)

            # if the vertex can generate a DSG, call it
            if isinstance(associated_vertex, AbstractDataSpecableVertex):

                data_spec_file_path = \
                    associated_vertex.get_data_spec_file_path(
                        placement.x, placement.y, placement.p, hostname,
                        application_data_runtime_folder)
                app_data_file_path = \
                    associated_vertex.get_application_data_file_path(
                        placement.x, placement.y, placement.p, hostname,
                        application_data_runtime_folder)
                data_spec_reader = FileDataReader(data_spec_file_path)
                data_writer = FileDataWriter(app_data_file_path)

                # locate current memory requirement
                current_memory_available = SDRAM.DEFAULT_SDRAM_BYTES
                memory_tracker_key = (placement.x, placement.y)
                if memory_tracker_key in space_based_memory_tracker:
                    current_memory_available = space_based_memory_tracker[
                        memory_tracker_key]

                # generate a file writer for dse report (app pointer table)
                report_writer = None
                if write_text_specs:
                    new_report_directory = os.path.join(
                        self._report_default_directory, "data_spec_text_files")

                    if not os.path.exists(new_report_directory):
                        os.mkdir(new_report_directory)

                    file_name = "{}_DSE_report_for_{}_{}_{}.txt".format(
                        hostname, placement.x, placement.y, placement.p)
                    report_file_path = os.path.join(new_report_directory,
                                                    file_name)
                    report_writer = FileDataWriter(report_file_path)

                # generate data spec executor
                host_based_data_spec_executor = DataSpecificationExecutor(
                    data_spec_reader, data_writer, current_memory_available,
                    report_writer)

                # update memory calc and run data spec executor
                try:
                    bytes_used_by_spec, bytes_written_by_spec = \
                        host_based_data_spec_executor.execute()
                except:
                    logger.error("Error executing data specification for {}"
                                 .format(associated_vertex))
                    traceback.print_exc()

                # update base address mapper
                processor_mapping_key = (placement.x, placement.y, placement.p)
                processor_to_app_data_base_address[processor_mapping_key] = {
                    'start_address':
                        ((SDRAM.DEFAULT_SDRAM_BYTES -
                          current_memory_available) +
                         constants.SDRAM_BASE_ADDR),
                    'memory_used': bytes_used_by_spec,
                    'memory_written': bytes_written_by_spec}

                space_based_memory_tracker[memory_tracker_key] = \
                    current_memory_available - bytes_used_by_spec

            # update the progress bar
            progress_bar.update()

        # close the progress bar
        progress_bar.end()
        return processor_to_app_data_base_address

    @staticmethod
    def _get_processors(executable_targets):
        # deduce how many processors this application uses up
        total_processors = 0
        all_core_subsets = list()
        for executable_target in executable_targets:
            core_subsets = executable_targets[executable_target]
            for core_subset in core_subsets:
                for _ in core_subset.processor_ids:
                    total_processors += 1
                all_core_subsets.append(core_subset)

        return total_processors, all_core_subsets

    def _wait_for_cores_to_be_ready(self, executable_targets, app_id):

        total_processors, all_core_subsets = self._get_processors(
            executable_targets)

        processor_c_main = self._txrx.get_core_state_count(app_id,
                                                           CPUState.C_MAIN)
        # check that everything has gone though c main to reach sync0 or
        # failing for some unknown reason
        while processor_c_main != 0:
            time.sleep(0.1)
            processor_c_main = self._txrx.get_core_state_count(app_id,
                                                               CPUState.C_MAIN)

        # check that the right number of processors are in sync0
        processors_ready = self._txrx.get_core_state_count(app_id,
                                                           CPUState.SYNC0)

        if processors_ready != total_processors:
            successful_cores, unsuccessful_cores = \
                self._break_down_of_failure_to_reach_state(all_core_subsets,
                                                           CPUState.SYNC0)

            # last chance to slip out of error check
            if len(successful_cores) != total_processors:
                # break_down the successful cores and unsuccessful cores into
                # string
                break_down = self.turn_break_downs_into_string(
                    all_core_subsets, successful_cores, unsuccessful_cores,
                    CPUState.SYNC0)
                raise exceptions.ExecutableFailedToStartException(
                    "Only {} processors out of {} have successfully reached "
                    "sync0 with breakdown of: {}"
                    .format(processors_ready, total_processors, break_down))

    def _start_all_cores(self, executable_targets, app_id):

        total_processors, all_core_subsets = self._get_processors(
            executable_targets)

        # if correct, start applications
        logger.info("Starting application")
        self._txrx.send_signal(app_id, SCPSignal.SYNC0)

        # check all apps have gone into run state
        logger.info("Checking that the application has started")
        processors_running = self._txrx.get_core_state_count(app_id,
                                                             CPUState.RUNNING)
        processors_finished = self._txrx.get_core_state_count(app_id,
                                                              CPUState.FINSHED)
        if processors_running < total_processors:
            if processors_running + processors_finished >= total_processors:
                logger.warn("some processors finished between signal "
                            "transmissions. Could be a sign of an error")
            else:
                successful_cores, unsuccessful_cores = \
                    self._break_down_of_failure_to_reach_state(
                        all_core_subsets, CPUState.RUNNING)

                # break_down the successful cores and unsuccessful cores into
                # string reps
                break_down = self.turn_break_downs_into_string(
                    all_core_subsets, successful_cores, unsuccessful_cores,
                    CPUState.RUNNING)
                raise exceptions.ExecutableFailedToStartException(
                    "Only {} of {} processors started with breakdown {}"
                    .format(processors_running, total_processors, break_down))

    def _wait_for_execution_to_complete(
            self, executable_targets, app_id, runtime, time_scaling):

        total_processors, all_core_subsets = self._get_processors(
            executable_targets)

        time_to_wait = ((runtime * time_scaling) / 1000.0) + 1.0
        logger.info("Application started - waiting {} seconds for it to"
                    " stop".format(time_to_wait))
        time.sleep(time_to_wait)
        processors_not_finished = total_processors
        while processors_not_finished != 0:
            processors_not_finished = self._txrx.get_core_state_count(
                app_id, CPUState.RUNNING)
            processors_rte = self._txrx.get_core_state_count(
                app_id, CPUState.RUN_TIME_EXCEPTION)
            if processors_rte > 0:
                successful_cores, unsuccessful_cores = \
                    self._break_down_of_failure_to_reach_state(
                        all_core_subsets, CPUState.RUNNING)

                # break_down the successful cores and unsuccessful cores
                # into string reps
                break_down = self.turn_break_downs_into_string(
                    all_core_subsets, successful_cores, unsuccessful_cores,
                    CPUState.RUNNING)
                raise exceptions.ExecutableFailedToStopException(
                    "{} cores have gone into a run time error state with "
                    "breakdown {}.".format(processors_rte, break_down))
            logger.info("Simulation still not finished or failed - "
                        "waiting a bit longer...")
            time.sleep(0.5)

        processors_exited = self._txrx.get_core_state_count(
            app_id, CPUState.FINSHED)

        if processors_exited < total_processors:
            successful_cores, unsuccessful_cores = \
                self._break_down_of_failure_to_reach_state(
                    all_core_subsets, CPUState.RUNNING)

            # break_down the successful cores and unsuccessful cores into
            #  string reps
            break_down = self.turn_break_downs_into_string(
                all_core_subsets, successful_cores, unsuccessful_cores,
                CPUState.RUNNING)
            raise exceptions.ExecutableFailedToStopException(
                "{} of the processors failed to exit successfully with"
                " breakdown {}.".format(
                    total_processors - processors_exited, break_down))
        logger.info("Application has run to completion")

    def _break_down_of_failure_to_reach_state(self, total_cores, state):
        successful_cores = list()
        unsuccessful_cores = dict()
        core_infos = self._txrx.get_cpu_information(total_cores)
        for core_info in core_infos:
            if core_info.state == state:
                successful_cores.append((core_info.x, core_info.y,
                                         core_info.p))
            else:
                unsuccessful_cores[(core_info.x, core_info.y, core_info.p)] = \
                    core_info
        return successful_cores, unsuccessful_cores

    @staticmethod
    def turn_break_downs_into_string(total_cores, successful_cores,
                                     unsuccessful_cores, state):
        """

        :param total_cores:
        :param successful_cores:
        :param unsuccessful_cores:
        :param state:
        :return:
        """
        break_down = os.linesep
        for core_info in total_cores:
            for processor_id in core_info.processor_ids:
                core_coord = (core_info.x, core_info.y, processor_id)
                if core_coord in successful_cores:
                    break_down += "{}:{}:{} successfully in state {}{}"\
                        .format(core_info.x, core_info.y, processor_id,
                                state.name, os.linesep)
                else:
                    real_state = unsuccessful_cores[(core_info.x, core_info.y,
                                                     processor_id)]
                    if real_state.state == CPUState.RUN_TIME_EXCEPTION:
                        break_down += \
                            ("{}:{}:{} failed to be in state {} and was"
                             " in state {}:{} instead{}".format
                             (core_info.x, core_info.y, processor_id,
                              state, real_state.state.name,
                              real_state.run_time_error.name, os.linesep))
                    else:
                        break_down += \
                            ("{}:{}:{} failed to be in state {} and was"
                             " in state {} instead{}".format
                             (core_info.x, core_info.y, processor_id,
                              state, real_state.state.name, os.linesep))
        return break_down

    def _load_application_data(
            self, placements, router_tables, vertex_to_subvertex_mapper,
            processor_to_app_data_base_address, hostname, app_id,
            app_data_folder, machine_version):

        # if doing reload, start script
        if self._reports_states.transciever_report:
            reports.start_transceiver_rerun_script(
                app_data_folder, hostname, machine_version)

        # go through the placements and see if there's any application data to
        # load
        progress_bar = ProgressBar(len(list(placements.placements)),
                                   "Loading application data onto the machine")
        for placement in placements.placements:
            associated_vertex = \
                vertex_to_subvertex_mapper.get_vertex_from_subvertex(
                    placement.subvertex)

            if isinstance(associated_vertex, AbstractDataSpecableVertex):
                logger.debug("loading application data for vertex {}"
                             .format(associated_vertex.label))
                key = (placement.x, placement.y, placement.p)
                start_address = \
                    processor_to_app_data_base_address[key]['start_address']
                memory_written = \
                    processor_to_app_data_base_address[key]['memory_written']
                file_path_for_application_data = \
                    associated_vertex.get_application_data_file_path(
                        placement.x, placement.y, placement.p, hostname,
                        app_data_folder)
                application_data_file_reader = SpinnmanFileDataReader(
                    file_path_for_application_data)
                logger.debug("writing application data for vertex {}"
                             .format(associated_vertex.label))
                self._txrx.write_memory(
                    placement.x, placement.y, start_address,
                    application_data_file_reader, memory_written)

                # update user 0 so that it points to the start of the
                # applications data region on sdram
                logger.debug("writing user 0 address for vertex {}"
                             .format(associated_vertex.label))
                user_o_register_address = \
                    self._txrx.get_user_0_register_address_from_core(
                        placement.x, placement.y, placement.p)
                self._txrx.write_memory(placement.x, placement.y,
                                        user_o_register_address, start_address)

                # add lines to rerun_script if requested
                if self._reports_states.transciever_report:
                    reports.re_load_script_application_data_load(
                        file_path_for_application_data, placement,
                        start_address, memory_written, user_o_register_address,
                        app_data_folder)
            progress_bar.update()
        progress_bar.end()

        progress_bar = ProgressBar(len(list(router_tables.routing_tables)),
                                   "Loading routing data onto the machine")

        # load each router table that is needed for the application to run into
        # the chips sdram
        for router_table in router_tables.routing_tables:
            if not self._machine.get_chip_at(router_table.x,
                                             router_table.y).virtual:
                self._txrx.clear_multicast_routes(router_table.x,
                                                  router_table.y)
                self._txrx.clear_router_diagnostic_counters(router_table.x,
                                                            router_table.y)

                if len(router_table.multicast_routing_entries) > 0:
                    self._txrx.load_multicast_routes(
                        router_table.x, router_table.y,
                        router_table.multicast_routing_entries, app_id=app_id)
                    if self._reports_states.transciever_report:
                        reports.re_load_script_load_routing_tables(
                            router_table, app_data_folder, app_id)
            progress_bar.update()
        progress_bar.end()

    def _load_executable_images(self, executable_targets, app_id,
                                app_data_folder):
        """ Go through the executable targets and load each binary to \
            everywhere and then send a start request to the cores that \
            actually use it
        """
        if self._reports_states.transciever_report:
            reports.re_load_script_load_executables_init(
                app_data_folder, executable_targets)

        progress_bar = ProgressBar(len(executable_targets),
                                   "Loading executables onto the machine")
        for executable_target_key in executable_targets:
            file_reader = SpinnmanFileDataReader(executable_target_key)
            core_subset = executable_targets[executable_target_key]

            statinfo = os.stat(executable_target_key)
            size = statinfo.st_size

            # TODO there is a need to parse the binary and see if its
            # ITCM and DTCM requirements are within acceptable params for
            # operating on spinnaker. Currnently there jsut a few safety
            # checks which may not be accurate enough.
            if size > constants.MAX_SAFE_BINARY_SIZE:
                logger.warn(
                    "The size of this binary is large enough that its"
                    " possible that the binary may be larger than what is"
                    " supported by spinnaker currently. Please reduce the"
                    " binary size if it starts to behave strangely, or goes"
                    " into the wdog state before starting.")
                if size > constants.MAX_POSSIBLE_BINARY_SIZE:
                    raise exceptions.ConfigurationException(
                        "The size of the binary is too large and therefore"
                        " will very likely cause a WDOG state. Until a more"
                        " precise measurement of ITCM and DTCM can be produced"
                        " this is deemed as an error state. Please reduce the"
                        " size of your binary or circumvent this error check.")

            self._txrx.execute_flood(core_subset, file_reader, app_id,
                                     size)

            if self._reports_states.transciever_report:
                reports.re_load_script_load_executables_individual(
                    app_data_folder, executable_target_key,
                    app_id, size)
            progress_bar.update()
        progress_bar.end()
