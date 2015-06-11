"""
configuration class for common front ends
"""

# front end common imports
from spinn_front_end_common.utilities.report_states import ReportState
from spinn_front_end_common.utilities import helpful_functions

# pacman inports
from pacman.operations import partition_algorithms
from pacman.operations import placer_algorithms
from pacman.operations import router_algorithms
from pacman.operations import routing_info_allocator_algorithms
from pacman.operations import tag_allocator_algorithms
from pacman.model.partitionable_graph.partitionable_graph import \
    PartitionableGraph


# general imports
import os
import datetime
import shutil
import logging
import tempfile

logger = logging.getLogger(__name__)


class FrontEndCommonConfigurationFunctions(object):
    """
    FrontEndCommonConfigurationFunctions : api inrt
    """

    def __init__(self, host_name, graph_label):

        # machine specific bits
        self._hostname = host_name
        self._time_scale_factor = None
        self._machine_time_step = None
        self._runtime = None

        # specific utility vertexes
        self._live_spike_recorder = dict()
        self._multi_cast_vertex = None
        self._txrx = None

        # debug flag
        self._in_debug_mode = None

        # main objects
        self._partitionable_graph = PartitionableGraph(label=graph_label)
        self._partitioned_graph = None
        self._graph_mapper = None
        self._no_machine_time_steps = None
        self._placements = None
        self._router_tables = None
        self._routing_infos = None
        self._pruner_infos = None
        self._has_ran = False
        self._reports_states = None
        self._app_id = None
        self._tags = None

        # pacman mapping objects
        self._partitioner_algorithm = None
        self._placer_algorithm = None
        self._tag_allocator_algorithm = None
        self._key_allocator_algorithm = None
        self._router_algorithm = None

        # Output objects
        self._report_folder = None
        self._output_folder = None
        self._write_text_specs = None

        # Run time string - used for file names
        this_run_time = datetime.datetime.now()
        self._this_run_time_string = (
            "{:04}-{:02}-{:02}-{:02}-{:02}-{:02}".format(
                this_run_time.year, this_run_time.month, this_run_time.day,
                this_run_time.hour, this_run_time.minute,
                this_run_time.second))

        # executable params
        self._do_load = None
        self._do_run = None
        self._retrieve_provance_data = True

        # helper data stores
        self._current_max_tag_value = 0

    def _write_timestamp_file(self, folder):
        """ Write a file containing the timestamp string for this run

        :param folder: The folder where the file should be written
        """
        timestamp_filename = os.path.join(folder, "time_stamp")
        writer = open(timestamp_filename, "w")
        writer.writelines(self._this_run_time_string)
        writer.close()

    def _set_up_output(self, output_folder, max_to_keep, sub_folder_name=None):
        """ Set up an output folder for some sort of data, with some\
            historical storage of past runs

        :param output_folder: Specification of where the output is to be\
                written.  This can be a specific folder for the output, \
                "DEFAULT", in which case the output is written to the current\
                working directory, or "TEMP", in which case the output is\
                written to a folder in the system temporary directory
        :param max_to_keep: The maximum number of historical runs to be kept
        :param sub_folder_name: The name of the folder to be created if \
                output_folder is "DEFAULT" or "TEMP"; ignored otherwise
        """
        output_data_folder = None
        if output_folder == "DEFAULT":
            output_data_folder = os.path.join(os.getcwd(), sub_folder_name)
        elif output_folder == "TEMP":
            output_data_folder = os.path.join(tempfile.gettempdir(),
                                              sub_folder_name)
        else:
            output_data_folder = output_folder

        if not os.path.exists(output_data_folder):
            os.makedirs(output_data_folder)

        self._output_folder = os.path.join(output_data_folder, "latest")
        if os.path.exists(self._output_folder):
            self._rotate_files(output_data_folder, max_to_keep)
        self._write_timestamp_file(self._output_folder)

    def _set_up_application_data_output(
            self, output_folder, max_to_keep):
        """ Set up the output of application data

        :param output_folder: The output folder specification for the data;\
                see _set_up_output for description
        :param max_to_keep: The maximum number of historical runs to keep
        """
        self._set_up_output(output_folder, max_to_keep,
                            'application_generated_data_files')

    def _set_up_report_output(self, reports_enabled, write_text_specs,
                              write_provance_data, report_folder, max_to_keep):
        """

        :param reports_are_enabled:
        :param write_text_specs:
        :param default_report_file_path:
        :param max_reports_kept:
        :param write_provance_data:
        :return:
        """
        self._write_text_specs = write_text_specs and reports_enabled
        self._retrieve_provance_data = write_provance_data and reports_enabled
        self._set_up_output(report_folder, max_to_keep, "reports")

    def _set_up_main_objects(
            self, reports_are_enabled, app_id, execute_partitioner_report,
            execute_placer_report, execute_router_report,
            execute_router_dat_based_report, execute_routing_info_report,
            execute_data_spec_report, execute_write_reload_steps,
            generate_transciever_report, generate_tag_report,
            generate_performance_measurements, in_debug_mode):
        """

        :param reports_are_enabled:
        :param app_id:
        :param execute_partitioner_report:
        :param execute_placer_report:
        :param execute_router_report:
        :param execute_router_dat_based_report:
        :param execute_routing_info_report:
        :param execute_data_spec_report:
        :param execute_write_reload_steps:
        :param generate_transciever_report:
        :param generate_performance_measurements:
        :param in_debug_mode:
        :return:
        """
        self._in_debug_mode = in_debug_mode

        # report object
        if reports_are_enabled:
            self._reports_states = ReportState(
                execute_partitioner_report, execute_placer_report,
                execute_router_report, execute_router_dat_based_report,
                execute_routing_info_report, execute_data_spec_report,
                execute_write_reload_steps, generate_transciever_report,
                generate_performance_measurements, generate_tag_report)

        # communication objects
        self._iptags = list()
        self._app_id = app_id

    def _set_up_executable_specifics(self, load_machine=True,
                                     run_machine=True):
        """

        :param load_machine:
        :param run_machine:
        :return:
        """
        # loading and running config params
        self._do_load = load_machine
        self._do_run = run_machine

    def _set_up_pacman_algorthms_listings(
            self, partitioner_algorithm=None, placer_algorithm=None,
            key_allocator_algorithm=None, routing_algorithm=None,
            tag_allocator_algorithm=None):
        """

        :param partitioner_algorithm:
        :param placer_algorithm:
        :param key_allocator_algorithm:
        :param routing_algorithm:
        :param tag_allocator_algorithm
        :return:
        """

        # algorithm lists
        if partitioner_algorithm is not None:
            partitioner_algorithms = helpful_functions.get_valid_components(
                partition_algorithms, "Partitioner")
            self._partitioner_algorithm = partitioner_algorithms[
                partitioner_algorithm]

        if placer_algorithm is not None:
            place_algorithms = helpful_functions.get_valid_components(
                placer_algorithms, "Placer")
            self._placer_algorithm = place_algorithms[placer_algorithm]

        if tag_allocator_algorithm is not None:
            tag_algorithms = helpful_functions.get_valid_components(
                tag_allocator_algorithms, "TagAllocator")
            self._tag_allocator_algorithm = tag_algorithms[
                tag_allocator_algorithm]

        # get common key allocator algorithms
        if key_allocator_algorithm is not None:
            key_allocator_algorithms = helpful_functions.get_valid_components(
                routing_info_allocator_algorithms, "RoutingInfoAllocator")
            self._key_allocator_algorithm = key_allocator_algorithms[
                key_allocator_algorithm]

        if routing_algorithm is not None:
            routing_algorithms = helpful_functions.get_valid_components(
                router_algorithms, "Routing")
            self._router_algorithm = routing_algorithms[routing_algorithm]

    @staticmethod
    def _rotate_files(starting_directory, max_to_keep):
        folder_name = os.path.join(starting_directory, "latest")
        timestamp_file = os.path.join(folder_name, "time_stamp")
        if os.path.isfile(timestamp_file):
            time_stamp_in = open(timestamp_file, "r")
            time_stamp_in_string = time_stamp_in.readline()
            time_stamp_in.close()
            os.remove(timestamp_file)
            new_folder = os.path.join(starting_directory,
                                      time_stamp_in_string)
            extra = 2
            while os.path.exists(new_folder):
                new_folder = os.path.join(
                    starting_directory,
                    time_stamp_in_string + "_" + str(extra))
                extra += 1
            shutil.move(folder_name, new_folder)

            # while there's more than the valid max, remove the oldest one
            files_in_report_folder = os.listdir(starting_directory)
            files_in_report_folder.sort(
                cmp,
                key=lambda temp_file: os.path.getmtime(
                    os.path.join(starting_directory, temp_file)))
            while len(files_in_report_folder) > max_to_keep:
                oldest_file = files_in_report_folder[0]
                shutil.rmtree(os.path.join(starting_directory, oldest_file),
                              ignore_errors=True)
                files_in_report_folder.remove(oldest_file)

    def set_runtime(self, value):
        """

        :param value:
        :return:
        """
        self._runtime = value
