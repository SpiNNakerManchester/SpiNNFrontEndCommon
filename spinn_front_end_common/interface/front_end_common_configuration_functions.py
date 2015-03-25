import os
import datetime
import shutil
import logging

from spinn_front_end_common.utilities.report_states import ReportState
from spinn_front_end_common.utilities import helpful_functions

from pacman.operations import partition_algorithms
from pacman.operations import placer_algorithms
from pacman.operations import router_algorithms
from pacman.operations import routing_info_allocator_algorithms
from pacman.model.partitionable_graph.partitionable_graph import \
    PartitionableGraph

logger = logging.getLogger(__name__)


class FrontEndCommonConfigurationFunctions(object):

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

        # pacman mapping objects
        self._partitioner_algorithm = None
        self._placer_algorithm = None
        self._key_allocator_algorithm = None
        self._router_algorithm = None
        self._report_default_directory = None
        self._app_data_runtime_folder = None
        self._this_run_time_string_representation = None

        # exeuctable params
        self._do_load = None
        self._do_run = None
        self._writeTextSpecs = None
        self._retrieve_provance_data = True

        # helper data stores
        self._current_max_tag_value = 0

        # database objects
        self._create_database = False
        self._database_thread = None

    def _set_up_output_application_data_specifics(
            self, where_to_write_application_data_files,
            max_application_binaries_kept):
        created_folder = False
        this_run_time_folder = None
        if where_to_write_application_data_files == "DEFAULT":
            directory = os.getcwd()
            application_generated_data_file_folder = \
                os.path.join(directory, 'application_generated_data_files')
            if not os.path.exists(application_generated_data_file_folder):
                os.makedirs(application_generated_data_file_folder)
                created_folder = True

            if not created_folder:
                self._move_report_and_binary_files(
                    max_application_binaries_kept,
                    application_generated_data_file_folder)

            # add time stamped folder for this run
            this_run_time_folder = \
                os.path.join(application_generated_data_file_folder, "latest")
            if not os.path.exists(this_run_time_folder):
                os.makedirs(this_run_time_folder)

            # store timestamp in latest/time_stamp
            time_of_run_file_name = os.path.join(this_run_time_folder,
                                                 "time_stamp")
            writer = open(time_of_run_file_name, "w")
            writer.writelines("app_{}_{}".format(
                self._app_id, self._this_run_time_string_representation))
            writer.flush()
            writer.close()

        elif where_to_write_application_data_files == "TEMP":

            # just dont set the config param, code downstairs
            #  from here will create temp folders if needed
            pass
        else:

            # add time stamped folder for this run
            this_run_time_folder = \
                os.path.join(where_to_write_application_data_files, "latest")
            if not os.path.exists(this_run_time_folder):
                os.makedirs(this_run_time_folder)
            else:
                self._move_report_and_binary_files(
                    max_application_binaries_kept,
                    where_to_write_application_data_files)

            # store timestamp in latest/time_stamp
            time_of_run_file_name = os.path.join(this_run_time_folder,
                                                 "time_stamp")
            writer = open(time_of_run_file_name, "w")
            writer.writelines("app_{}_{}".format(
                self._app_id, self._this_run_time_string_representation))

            if not os.path.exists(this_run_time_folder):
                os.makedirs(this_run_time_folder)
        self._app_data_runtime_folder = this_run_time_folder

    def _set_up_report_specifics(self, reports_are_enabled, write_text_specs,
                                 default_report_file_path, max_reports_kept,
                                 write_provance_data):
        self._writeTextSpecs = False
        if reports_are_enabled:
            self._writeTextSpecs = write_text_specs

        # determine common report folder
        config_param = default_report_file_path
        created_folder = False
        if config_param == "DEFAULT":
            directory = os.getcwd()

            # global reports folder
            self._report_default_directory = os.path.join(directory, 'reports')
            if not os.path.exists(self._report_default_directory):
                os.makedirs(self._report_default_directory)
                created_folder = True
        elif config_param == "REPORTS":
            self._report_default_directory = 'reports'
            if not os.path.exists(self._report_default_directory):
                os.makedirs(self._report_default_directory)
        else:
            self._report_default_directory = \
                os.path.join(config_param, 'reports')
            if not os.path.exists(self._report_default_directory):
                os.makedirs(self._report_default_directory)

        # clear and clean out folders considered not useful anymore
        if not created_folder \
                and len(os.listdir(self._report_default_directory)) > 0:
            self._move_report_and_binary_files(max_reports_kept,
                                               self._report_default_directory)

        # handle timing app folder and cleaning of report folder from last run
        app_folder_name = os.path.join(self._report_default_directory,
                                       "latest")
        if not os.path.exists(app_folder_name):
                os.makedirs(app_folder_name)

        # store timestamp in latest/time_stamp
        time_of_run_file_name = os.path.join(app_folder_name, "time_stamp")
        writer = open(time_of_run_file_name, "w")

        # determine the time slot for later
        this_run_time = datetime.datetime.now()
        self._this_run_time_string_repenstation = \
            str(this_run_time.date()) + "-" + str(this_run_time.hour) + "-" + \
            str(this_run_time.minute) + "-" + str(this_run_time.second)
        writer.writelines("app_{}_{}".format(
            self._app_id, self._this_run_time_string_repenstation))
        writer.flush()
        writer.close()
        self._report_default_directory = app_folder_name
        self._retrieve_provance_data = write_provance_data

    def _set_up_main_objects(
            self, reports_are_enabled, app_id, execute_partitioner_report,
            execute_placer_report, execute_router_report,
            execute_router_dat_based_report, execute_routing_info_report,
            execute_data_spec_report, execute_write_reload_steps,
            generate_transciever_report,
            generate_performance_measurements,
            in_debug_mode, create_database):
        self._in_debug_mode = in_debug_mode

        # report object
        if reports_are_enabled:
            self._reports_states = ReportState(
                execute_partitioner_report, execute_placer_report,
                execute_router_report, execute_router_dat_based_report,
                execute_routing_info_report, execute_data_spec_report,
                execute_write_reload_steps, generate_transciever_report,
                generate_performance_measurements)

        self._create_database = create_database

        # communication objects
        self._iptags = list()
        self._app_id = app_id

    def _set_up_executable_specifics(self, load_machine=True,
                                     run_machine=True):
        # loading and running config params
        self._do_load = load_machine
        self._do_run = run_machine

    def _set_up_pacman_algorthms_listings(
            self, partitioner_algorithm=None, placer_algorithm=None,
            key_allocator_algorithm=None, routing_algorithm=None):

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
    def _move_report_and_binary_files(max_to_keep, starting_directory):
        app_folder_name = os.path.join(starting_directory, "latest")
        app_name_file = os.path.join(app_folder_name, "time_stamp")
        if os.path.isfile(app_name_file):
            time_stamp_in = open(app_name_file, "r")
            time_stamp_in_string = time_stamp_in.readline()
            time_stamp_in.close()
            os.remove(app_name_file)
            new_app_folder = os.path.join(starting_directory,
                                          time_stamp_in_string)
            extra = 2
            while os.path.exists(new_app_folder):
                new_app_folder = os.path.join(
                    starting_directory,
                    time_stamp_in_string + "_" + str(extra))
                extra += 1

            os.makedirs(new_app_folder)
            list_of_files = os.listdir(app_folder_name)
            for file_to_move in list_of_files:
                file_path = os.path.join(app_folder_name, file_to_move)
                shutil.move(file_path, new_app_folder)
            files_in_report_folder = os.listdir(starting_directory)

            # while theres more than the valid max, remove the oldest one
            while len(files_in_report_folder) > max_to_keep:
                files_in_report_folder.sort(
                    cmp, key=lambda temp_file:
                    os.path.getmtime(os.path.join(starting_directory,
                                                  temp_file)))
                oldest_file = files_in_report_folder[0]
                shutil.rmtree(os.path.join(starting_directory, oldest_file),
                              ignore_errors=True)
                files_in_report_folder.remove(oldest_file)

    def set_runtime(self, value):
        self._runtime = value
