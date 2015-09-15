"""
interface for communciating with spinnaker machine easily.
"""
from data_specification.data_specification_executor import \
    DataSpecificationExecutor
from data_specification.exceptions import DataSpecificationException
from data_specification.file_data_writer import FileDataWriter
from data_specification.file_data_reader import FileDataReader

# pacman imports
from pacman.utilities.progress_bar import ProgressBar

# spinnmachine imports
from spinn_machine.virutal_machine import VirtualMachine

# spinnman imports
from spinnman.messages.scp.scp_signal import SCPSignal
from spinnman.model.cpu_state import CPUState
from spinnman.transceiver import create_transceiver_from_hostname
from spinnman.data.file_data_reader import FileDataReader \
    as SpinnmanFileDataReader
from spinnman.model.core_subsets import CoreSubsets
from spinnman.model.core_subset import CoreSubset
from spinnman import constants as spinnman_constants
from spinnman.model.bmp_connection_data import BMPConnectionData

# front end common imports
from spinn_front_end_common.abstract_models.abstract_data_specable_vertex \
    import AbstractDataSpecableVertex
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities.reload.reload_script import ReloadScript
from spinn_front_end_common.interface.buffer_management.buffer_manager import \
    BufferManager
from spinn_front_end_common.interface.buffer_management.buffer_models.\
    abstract_sends_buffers_from_host_partitioned_vertex import \
    AbstractSendsBuffersFromHostPartitionedVertex
from spinn_front_end_common.utility_models.live_packet_gather import \
    LivePacketGather
from spinn_front_end_common.utility_models.reverse_ip_tag_multi_cast_source \
    import ReverseIpTagMultiCastSource

# general imports
import time
import os
import logging
import re
from collections import OrderedDict

logger = logging.getLogger(__name__)


class FrontEndCommonInterfaceFunctions(object):
    """
    the front end common interface which supports functions such as :
    setting up the python spinnMachine
    writing data to spinnaker machine
    loading tags
    etc
    """

    def __init__(self, reports_states, report_default_directory,
                 app_data_folder):
        self._reports_states = reports_states
        self._report_default_directory = report_default_directory
        self._machine = None
        self._app_data_folder = app_data_folder
        self._reload_script = None
        self._send_buffer_manager = None

    def _auto_detect_database(self, partitioned_graph):
        """
        autodetects if there is a need to activate the database system
        :param partitioned_graph: the partitioned graph of the application
        problem space.
        :return: a bool which represents if the database is needed
        """
        for vertex in partitioned_graph.subvertices:
            if (isinstance(vertex, LivePacketGather) or
                    isinstance(vertex, ReverseIpTagMultiCastSource)):
                return True
        else:
            return False

    def setup_interfaces(
            self, hostname, bmp_details, downed_chips, downed_cores,
            board_version, number_of_boards, width, height,
            is_virtual, virtual_has_wrap_arounds, auto_detect_bmp=True,
            enable_reinjection=True):
        """
        Set up the interfaces for communicating with the SpiNNaker board
        :param hostname: the hostname or ip address of the spinnaker machine
        :param bmp_details: the details of the BMP connections
        :param downed_chips: the chips that are down which sark thinks are\
                alive
        :param downed_cores: the cores that are down which sark thinks are\
                alive
        :param board_version: the version of the boards being used within the\
                machine (1, 2, 3, 4 or 5)
        :param number_of_boards: the number of boards within the machine
        :param width: The width of the machine in chips
        :param height: The height of the machine in chips
        :param is_virtual: True of the machine is virtual, False otherwise; if\
                True, the width and height are used as the machine dimensions
        :param virtual_has_wrap_arounds: True if the machine is virtual and\
                should be created with wrap_arounds
        :param auto_detect_bmp: boolean which determines if the bmp should
               be automatically determined
        :param enable_reinjection: True if dropped packet reinjection is to be\
               enabled
        :return: None
        """

        if not is_virtual:
            # sort out down chips and down cores if needed
            ignored_chips, ignored_cores = \
                self._sort_out_downed_chips_cores(downed_chips, downed_cores)

            # sort out bmp connections into list of strings
            bmp_connection_data = self._sort_out_bmp_string(bmp_details)

            self._txrx = create_transceiver_from_hostname(
                hostname=hostname, bmp_connection_data=bmp_connection_data,
                version=board_version, ignore_chips=ignored_chips,
                ignore_cores=ignored_cores, number_of_boards=number_of_boards,
                auto_detect_bmp=auto_detect_bmp)

            # update number of boards from machine
            if number_of_boards is None:
                number_of_boards = self._txrx.number_of_boards_located

            # do autoboot if possible
            if board_version is None:
                raise exceptions.ConfigurationException(
                    "Please set a machine version number in the configuration "
                    "file (spynnaker.cfg or pacman.cfg)")
            self._txrx.ensure_board_is_ready(
                number_of_boards, width, height,
                enable_reinjector=enable_reinjection)
            self._txrx.discover_scamp_connections()
            self._machine = self._txrx.get_machine_details()
            if self._reports_states.transciever_report:
                self._reload_script = ReloadScript(
                    self._app_data_folder, hostname, board_version,
                    bmp_details, downed_chips, downed_cores, number_of_boards,
                    height, width, auto_detect_bmp, enable_reinjection)
        else:
            self._machine = VirtualMachine(
                width=width, height=height,
                with_wrap_arounds=virtual_has_wrap_arounds)

    @staticmethod
    def _sort_out_bmp_cabinet_and_frame_string(bmp_cabinet_and_frame):
        split_string = bmp_cabinet_and_frame.split(";", 2)
        if len(split_string) == 1:
            return [0, 0, split_string[0]]
        if len(split_string) == 2:
            return [0, split_string[0], split_string[1]]
        return [split_string[0], split_string[1], split_string[2]]

    @staticmethod
    def _sort_out_bmp_boards_string(bmp_boards):

        # If the string is a range of boards, get the range
        range_match = re.match("(\d+)-(\d+)", bmp_boards)
        if range_match is not None:
            return range(int(range_match.group(1)),
                         int(range_match.group(2)) + 1)

        # Otherwise, assume a list of boards
        return [int(board) for board in bmp_boards.split(",")]

    @staticmethod
    def _sort_out_bmp_string(bmp_string):
        """ Take a BMP line and split it into the BMP connection data
        :param bmp_string: the BMP string to be converted
        :return: the BMP connection data
        """
        bmp_details = list()
        if bmp_string == "None":
            return bmp_details

        for bmp_detail in bmp_string.split(":"):

            bmp_string_split = bmp_detail.split("/")
            (cabinet, frame, hostname) = FrontEndCommonInterfaceFunctions.\
                _sort_out_bmp_cabinet_and_frame_string(bmp_string_split[0])

            if len(bmp_string_split) == 1:

                # if there is no split, then assume its one board,
                # located at position 0
                bmp_details.append(
                    BMPConnectionData(cabinet, frame, hostname, [0]))
            else:
                boards = FrontEndCommonInterfaceFunctions.\
                    _sort_out_bmp_boards_string(bmp_string_split[1])

                bmp_details.append(
                    BMPConnectionData(cabinet, frame, hostname, boards))
        return bmp_details

    @staticmethod
    def _sort_out_downed_chips_cores(downed_chips, downed_cores):
        """
        translates the down cores and down chips string into stuff spinnman
        can understand
        :param downed_cores: string representing down cores
        :type downed_cores: str
        :param downed_chips: string representing down chips
        :type: downed_chips: str
        :return: a list of down cores and down chips in processor and coreset
        format
        """
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
        return ignored_chips, ignored_cores

    def set_up_send_buffering(self, partitioned_graph, placements, tags):
        """
        interface for buffered vertices
        :param partitioned_graph: the partitioned graph object
        :param placements: the placements object
        :param tags: the tags object
        :return: None
        """
        progress_bar = ProgressBar(
            len(partitioned_graph.subvertices), "Initialising buffers")

        # Create the buffer manager
        self._send_buffer_manager = BufferManager(
            placements, tags, self._txrx, self._reports_states,
            self._app_data_folder, self._reload_script)

        for partitioned_vertex in partitioned_graph.subvertices:
            if isinstance(partitioned_vertex,
                          AbstractSendsBuffersFromHostPartitionedVertex):

                # Add the vertex to the managed vertices
                self._send_buffer_manager.add_sender_vertex(
                    partitioned_vertex)
            progress_bar.update()
        progress_bar.end()

    def load_tags(self, tags):
        """ loads all the tags onto all the boards
        :param tags: the tags object which contains ip and reverse ip tags.
        :return none
        """
        # clear all the tags from the ethernet connection, as nothing should
        # be allowed to use it (no two sims should use the same etiehrnet
        # connection at the same time
        for tag_id in range(spinnman_constants.MAX_TAG_ID):
            self._txrx.clear_ip_tag(tag_id)

        self.load_iptags(tags.ip_tags)
        self.load_reverse_iptags(tags.reverse_ip_tags)

    def load_iptags(self, iptags):
        """
        loads all the iptags individually.
        :param iptags: the iptags to be loaded.
        :return: none
        """
        for ip_tag in iptags:
            self._txrx.set_ip_tag(ip_tag)
            if self._reports_states.transciever_report:
                self._reload_script.add_ip_tag(ip_tag)

    def load_reverse_iptags(self, reverse_ip_tags):
        """
        loads all the reverse iptags individually.
        :param reverse_ip_tags: the reverse iptags to be loaded
        :return: None
        """
        for reverse_ip_tag in reverse_ip_tags:
            self._txrx.set_reverse_ip_tag(reverse_ip_tag)
            if self._reports_states.transciever_report:
                self._reload_script.add_reverse_ip_tag(reverse_ip_tag)

    def execute_data_specification_execution(
            self, host_based_execution, hostname, placements, graph_mapper,
            write_text_specs, runtime_application_data_folder, machine):
        """

        :param host_based_execution:
        :param hostname:
        :param placements:
        :param graph_mapper:
        :param write_text_specs:
        :param runtime_application_data_folder:
        :param machine:
        :return:
        """
        if host_based_execution:
            return self.host_based_data_specification_execution(
                hostname, placements, graph_mapper, write_text_specs,
                runtime_application_data_folder, machine)
        else:
            return self._chip_based_data_specification_execution(hostname)

    def _chip_based_data_specification_execution(self, hostname):
        raise NotImplementedError

    def host_based_data_specification_execution(
            self, hostname, placements, graph_mapper, write_text_specs,
            application_data_runtime_folder, machine):
        """

        :param hostname:
        :param placements:
        :param graph_mapper:
        :param write_text_specs:
        :param application_data_runtime_folder:
        :param machine:
        :return:
        """
        next_position_tracker = dict()
        space_available_tracker = dict()
        processor_to_app_data_base_address = dict()

        # create a progress bar for end users
        progress_bar = ProgressBar(len(list(placements.placements)),
                                   "Executing data specifications")

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
                chip = machine.get_chip_at(placement.x, placement.y)
                next_position = chip.sdram.user_base_address
                space_available = chip.sdram.size
                placement_key = (placement.x, placement.y)
                if placement_key in next_position_tracker:
                    next_position = next_position_tracker[placement_key]
                    space_available = space_available_tracker[placement_key]

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
                    data_spec_reader, data_writer, space_available,
                    report_writer)

                # update memory calc and run data spec executor
                bytes_used_by_spec = 0
                bytes_written_by_spec = 0
                try:
                    bytes_used_by_spec, bytes_written_by_spec = \
                        host_based_data_spec_executor.execute()
                except DataSpecificationException as e:
                    logger.error("Error executing data specification for {}"
                                 .format(associated_vertex))
                    raise e

                # update base address mapper
                processor_mapping_key = (placement.x, placement.y, placement.p)
                processor_to_app_data_base_address[processor_mapping_key] = {
                    'start_address': next_position,
                    'memory_used': bytes_used_by_spec,
                    'memory_written': bytes_written_by_spec}

                next_position_tracker[placement_key] = (next_position +
                                                        bytes_used_by_spec)
                space_available_tracker[placement_key] = (space_available -
                                                          bytes_used_by_spec)

            # update the progress bar
            progress_bar.update()

        # close the progress bar
        progress_bar.end()
        return processor_to_app_data_base_address

    def wait_for_cores_to_be_ready(self, executable_targets, app_id):

        total_processors = executable_targets.total_processors
        all_core_subsets = executable_targets.all_core_subsets

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
            unsuccessful_cores = self._get_cores_not_in_state(
                all_core_subsets, CPUState.SYNC0)

            # last chance to slip out of error check
            if len(unsuccessful_cores) != 0:
                break_down = self._get_core_status_string(unsuccessful_cores)
                raise exceptions.ExecutableFailedToStartException(
                    "Only {} processors out of {} have successfully reached "
                    "SYNC0:{}".format(
                        processors_ready, total_processors, break_down))

    def start_all_cores(self, executable_targets, app_id):
        """

        :param executable_targets:
        :param app_id:
        :return:
        """

        total_processors = executable_targets.total_processors
        all_core_subsets = executable_targets.all_core_subsets

        # if correct, start applications
        logger.info("Starting application")
        self._txrx.send_signal(app_id, SCPSignal.SYNC0)

        # check all apps have gone into run state
        logger.info("Checking that the application has started")
        processors_running = self._txrx.get_core_state_count(
            app_id, CPUState.RUNNING)
        if processors_running < total_processors:

            processors_finished = self._txrx.get_core_state_count(
                app_id, CPUState.FINISHED)
            if processors_running + processors_finished >= total_processors:
                logger.warn("some processors finished between signal "
                            "transmissions. Could be a sign of an error")
            else:
                unsuccessful_cores = self._get_cores_not_in_state(
                    all_core_subsets, CPUState.RUNNING)
                break_down = self._get_core_status_string(
                    unsuccessful_cores)
                raise exceptions.ExecutableFailedToStartException(
                    "Only {} of {} processors started:{}"
                    .format(processors_running, total_processors, break_down))

    def wait_for_execution_to_complete(
            self, executable_targets, app_id, runtime, time_scaling):
        """

        :param executable_targets:
        :param app_id:
        :param runtime:
        :param time_scaling:
        :return:
        """

        total_processors = executable_targets.total_processors
        all_core_subsets = executable_targets.all_core_subsets

        time_to_wait = ((runtime * time_scaling) / 1000.0) + 1.0
        logger.info("Application started - waiting {} seconds for it to"
                    " stop".format(time_to_wait))
        time.sleep(time_to_wait)
        processors_not_finished = total_processors
        while processors_not_finished != 0:
            processors_rte = self._txrx.get_core_state_count(
                app_id, CPUState.RUN_TIME_EXCEPTION)
            if processors_rte > 0:
                rte_cores = self._get_cores_in_state(
                    all_core_subsets, CPUState.RUN_TIME_EXCEPTION)
                break_down = self._get_core_status_string(rte_cores)
                raise exceptions.ExecutableFailedToStopException(
                    "{} cores have gone into a run time error state:"
                    "{}".format(processors_rte, break_down))

            processors_not_finished = self._txrx.get_core_state_count(
                app_id, CPUState.RUNNING)
            if processors_not_finished > 0:
                logger.info("Simulation still not finished or failed - "
                            "waiting a bit longer...")
                time.sleep(0.5)

        processors_exited = self._txrx.get_core_state_count(
            app_id, CPUState.FINISHED)

        if processors_exited < total_processors:
            unsuccessful_cores = self._get_cores_not_in_state(
                all_core_subsets, CPUState.FINISHED)
            break_down = self._get_core_status_string(
                unsuccessful_cores)
            raise exceptions.ExecutableFailedToStopException(
                "{} of {} processors failed to exit successfully:"
                "{}".format(
                    total_processors - processors_exited, total_processors,
                    break_down))
        if self._reports_states.transciever_report:
            self._reload_script.close()
        if self._send_buffer_manager is not None:
            self._send_buffer_manager.stop()
        logger.info("Application has run to completion")

    def _get_cores_in_state(self, all_core_subsets, state):
        core_infos = self._txrx.get_cpu_information(all_core_subsets)
        cores_in_state = OrderedDict()
        for core_info in core_infos:
            if core_info.state == state:
                cores_in_state[
                    (core_info.x, core_info.y, core_info.p)] = core_info
        return cores_in_state

    def _get_cores_not_in_state(self, all_core_subsets, state):
        core_infos = self._txrx.get_cpu_information(all_core_subsets)
        cores_not_in_state = OrderedDict()
        for core_info in core_infos:
            if core_info.state != state:
                cores_not_in_state[
                    (core_info.x, core_info.y, core_info.p)] = core_info
        return cores_not_in_state

    @staticmethod
    def _get_core_status_string(core_infos):
        break_down = "\n"
        for ((x, y, p), core_info) in core_infos.iteritems():
            if core_info.state == CPUState.RUN_TIME_EXCEPTION:
                break_down += "    {}:{}:{} in state {}:{}\n".format(
                    x, y, p, core_info.state.name,
                    core_info.run_time_error.name)
            else:
                break_down += "    {}:{}:{} in state {}\n".format(
                    x, y, p, core_info.state.name)
        return break_down

    def _load_application_data(
            self, placements, vertex_to_subvertex_mapper,
            processor_to_app_data_base_address, hostname, app_data_folder,
            verify=False):

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
                application_data_file_reader.close()

                if verify:
                    application_data_file_reader = SpinnmanFileDataReader(
                        file_path_for_application_data)
                    all_data = application_data_file_reader.readall()
                    read_data = self._txrx.read_memory(
                        placement.x, placement.y, start_address,
                        memory_written)
                    if read_data != all_data:
                        raise Exception("Miswrite of {}, {}, {}, {}".format(
                            placement.x, placement.y, placement.p,
                            start_address))
                    application_data_file_reader.close()

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
                    self._reload_script.add_application_data(
                        file_path_for_application_data, placement,
                        start_address)
            progress_bar.update()
        progress_bar.end()

    def load_routing_tables(self, router_tables, app_id):
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
                        self._reload_script.add_routing_table(router_table)
            progress_bar.update()
        progress_bar.end()

    def load_executable_images(self, executable_targets, app_id):
        """ Go through the executable targets and load each binary to \
            everywhere and then send a start request to the cores that \
            actually use it
        """

        progress_bar = ProgressBar(executable_targets.total_processors,
                                   "Loading executables onto the machine")
        for executable_target_key in executable_targets.binary_paths():
            file_reader = SpinnmanFileDataReader(executable_target_key)
            core_subset = executable_targets.\
                retrieve_cores_for_a_executable_target(executable_target_key)

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
                self._reload_script.add_binary(executable_target_key,
                                               core_subset)
            acutal_cores_loaded = 0
            for chip_based in core_subset.core_subsets:
                for _ in chip_based.processor_ids:
                    acutal_cores_loaded += 1
            progress_bar.update(amount_to_add=acutal_cores_loaded)
        progress_bar.end()
