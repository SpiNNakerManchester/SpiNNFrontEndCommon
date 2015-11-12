
# front end common imports
from collections import OrderedDict
from spinn_front_end_common.utility_models.live_packet_gather import \
    LivePacketGather
from spinn_front_end_common.utility_models.\
    reverse_ip_tag_multi_cast_source import ReverseIpTagMultiCastSource
from spinn_front_end_common.interface import interface_functions
from spinn_front_end_common.utilities import report_functions as \
    front_end_common_report_functions

# pacman imports
from pacman.operations.pacman_algorithm_executor import PACMANAlgorithmExecutor

# general imports
import os
import datetime
import shutil
import logging
import re
import inspect
import struct

logger = logging.getLogger(__name__)


def get_valid_components(module, terminator):
    """
    ???????????????
    :param module:
    :param terminator:
    :return:
    """
    terminator = re.compile(terminator + '$')
    return dict(map(lambda (name, router): (terminator.sub('', name),
                                            router),
                inspect.getmembers(module, inspect.isclass)))


def read_data(x, y, address, length, data_format, transceiver):
    """ Reads and converts a single data item from memory
    :param x: chip x
    :param y: chip y
    :param address: base address of the sdram chip to read
    :param length: length to read
    :param data_format: the format to read memory
    :param transceiver: the spinnman interface
    """

    # turn byte array into str for unpack to work
    data = buffer(transceiver.read_memory(x, y, address, length))
    result = struct.unpack_from(data_format, data)[0]
    return result


def auto_detect_database(partitioned_graph):
    """ Auto detects if there is a need to activate the database system
    :param partitioned_graph: the partitioned graph of the application\
            problem space.
    :return: a bool which represents if the database is needed
    """
    for vertex in partitioned_graph.subvertices:
        if (isinstance(vertex, LivePacketGather) or
                isinstance(vertex, ReverseIpTagMultiCastSource)):
            return True
    else:
        return False


def set_up_output_application_data_specifics(
        where_to_write_application_data_files,
        max_application_binaries_kept, app_id, this_run_time_string):
    """

    :param where_to_write_application_data_files:
    :param max_application_binaries_kept:
    :param app_id:
    :param this_run_time_string:
    :return:
    """
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
            _move_report_and_binary_files(
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
            app_id, this_run_time_string))
        writer.flush()
        writer.close()

    elif where_to_write_application_data_files == "TEMP":

        # just don't set the config param, code downstairs
        # from here will create temp folders if needed
        pass
    else:

        # add time stamped folder for this run
        this_run_time_folder = \
            os.path.join(where_to_write_application_data_files, "latest")
        if not os.path.exists(this_run_time_folder):
            os.makedirs(this_run_time_folder)
        else:
            _move_report_and_binary_files(
                max_application_binaries_kept,
                where_to_write_application_data_files)

        # store timestamp in latest/time_stamp
        time_of_run_file_name = os.path.join(this_run_time_folder,
                                             "time_stamp")
        writer = open(time_of_run_file_name, "w")
        writer.writelines("app_{}_{}".format(
            app_id, this_run_time_string))

        if not os.path.exists(this_run_time_folder):
            os.makedirs(this_run_time_folder)
    return this_run_time_folder


def set_up_report_specifics(
        default_report_file_path, max_reports_kept, app_id):
    """

    :param default_report_file_path:
    :param max_reports_kept:
    :param app_id:
    :return:
    """

    # determine common report folder
    config_param = default_report_file_path
    created_folder = False
    if config_param == "DEFAULT":
        directory = os.getcwd()

        # global reports folder
        report_default_directory = os.path.join(directory, 'reports')
        if not os.path.exists(report_default_directory):
            os.makedirs(report_default_directory)
            created_folder = True
    elif config_param == "REPORTS":
        report_default_directory = 'reports'
        if not os.path.exists(report_default_directory):
            os.makedirs(report_default_directory)
    else:
        report_default_directory = \
            os.path.join(config_param, 'reports')
        if not os.path.exists(report_default_directory):
            os.makedirs(report_default_directory)

    # clear and clean out folders considered not useful anymore
    if not created_folder \
            and len(os.listdir(report_default_directory)) > 0:
        _move_report_and_binary_files(max_reports_kept,
                                      report_default_directory)

    # handle timing app folder and cleaning of report folder from last run
    app_folder_name = os.path.join(report_default_directory, "latest")
    if not os.path.exists(app_folder_name):
            os.makedirs(app_folder_name)

    # store timestamp in latest/time_stamp
    time_of_run_file_name = os.path.join(app_folder_name, "time_stamp")
    writer = open(time_of_run_file_name, "w")

    # determine the time slot for later
    this_run_time = datetime.datetime.now()
    this_run_time_string = (
        "{:04}-{:02}-{:02}-{:02}-{:02}-{:02}".format(
            this_run_time.year, this_run_time.month, this_run_time.day,
            this_run_time.hour, this_run_time.minute,
            this_run_time.second))
    writer.writelines("app_{}_{}".format(app_id,
                                         this_run_time_string))
    writer.flush()
    writer.close()
    return app_folder_name, this_run_time_string


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


def do_mapping(
        inputs, algorithms, required_outputs, xml_paths, do_timings):
    """
    :param do_timings: bool which sattes if each algorithm should time itself
    :param inputs:
    :param algorithms:
    :param required_outputs:
    :param xml_paths:
    :param in_debug_mode:
    :return:
    """

    # add xml path to front end common interfact functions
    xml_paths.append(
        os.path.join(os.path.dirname(interface_functions.__file__),
                     "front_end_common_interface_functions.xml"))

    # add xml path to front end common report functions
    xml_paths.append(
        os.path.join(os.path.dirname(
            front_end_common_report_functions.__file__),
            "front_end_common_reports.xml"))

    # create executor
    pacman_executor = PACMANAlgorithmExecutor(
        do_timings=do_timings, inputs=inputs, xml_paths=xml_paths,
        algorithms=algorithms, required_outputs=required_outputs)

    # execute mapping process
    pacman_executor.execute_mapping()

    return pacman_executor


def get_cores_in_state(all_core_subsets, state, txrx):
    """

    :param all_core_subsets:
    :param state:
    :param txrx:
    :return:
    """
    core_infos = txrx.get_cpu_information(all_core_subsets)
    cores_in_state = OrderedDict()
    for core_info in core_infos:
        if core_info.state == state:
            cores_in_state[
                (core_info.x, core_info.y, core_info.p)] = core_info
    return cores_in_state


def get_cores_not_in_state(all_core_subsets, state, txrx):
    """

    :param all_core_subsets:
    :param state:
    :param txrx:
    :return:
    """
    core_infos = txrx.get_cpu_information(all_core_subsets)
    cores_not_in_state = OrderedDict()
    for core_info in core_infos:
        if core_info.state != state:
            cores_not_in_state[
                (core_info.x, core_info.y, core_info.p)] = core_info
    return cores_not_in_state
