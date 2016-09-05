# dsg imports
from data_specification import utility_calls

# front end common imports
from spinn_front_end_common.interface import interface_functions
from spinn_front_end_common.utilities import report_functions as \
    front_end_common_report_functions
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities.utility_objs.executable_targets\
    import ExecutableTargets

# spinnman imports
from spinnman.model.cpu_state import CPUState
from spinn_machine.core_subsets import CoreSubsets
from spinn_machine.core_subset import CoreSubset

# general imports
import os
import datetime
import shutil
import logging
import re
import inspect
import struct
import time
from collections import OrderedDict

logger = logging.getLogger(__name__)


def get_valid_components(module, terminator):
    """ Get possible components

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
    :param address: base address of the SDRAM chip to read
    :param length: length to read
    :param data_format: the format to read memory
    :param transceiver: the SpinnMan interface
    """

    # turn byte array into str for unpack to work
    data = buffer(transceiver.read_memory(x, y, address, length))
    result = struct.unpack_from(data_format, data)[0]
    return result


def locate_memory_region_for_placement(placement, region, transceiver):
    """ Get the address of a region for a placement

    :param region: the region to locate the base address of
    :type region: int
    :param placement: the placement object to get the region address of
    :type placement: pacman.model.placements.placement.Placement
    :param transceiver: the python interface to the spinnaker machine
    :type transceiver: spiNNMan.transciever.Transciever
    :return: None
    """
    regions_base_address = transceiver.get_cpu_information_from_core(
        placement.x, placement.y, placement.p).user[0]

    # Get the position of the region in the pointer table
    region_offset_in_pointer_table = \
        utility_calls.get_region_base_address_offset(
            regions_base_address, region)
    region_address = buffer(transceiver.read_memory(
        placement.x, placement.y, region_offset_in_pointer_table, 4))
    region_address_decoded = struct.unpack_from("<I", region_address)[0]
    return region_address_decoded


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

        # while there's more than the valid max, remove the oldest one
        while len(files_in_report_folder) > max_to_keep:
            files_in_report_folder.sort(
                cmp, key=lambda temp_file:
                os.path.getmtime(os.path.join(starting_directory,
                                              temp_file)))
            oldest_file = files_in_report_folder[0]
            shutil.rmtree(os.path.join(starting_directory, oldest_file),
                          ignore_errors=True)
            files_in_report_folder.remove(oldest_file)


def get_front_end_common_pacman_xml_paths():
    """ Get the XML path for the front end common interface functions
    """
    return [
        os.path.join(
            os.path.dirname(interface_functions.__file__),
            "front_end_common_interface_functions.xml"),
        os.path.join(
            os.path.dirname(front_end_common_report_functions.__file__),
            "front_end_common_reports.xml")
    ]


def get_cores_in_state(all_core_subsets, states, txrx):
    """

    :param all_core_subsets:
    :param states:
    :param txrx:
    :return:
    """
    core_infos = txrx.get_cpu_information(all_core_subsets)
    cores_in_state = OrderedDict()
    for core_info in core_infos:
        if hasattr(states, "__iter__"):
            if core_info.state in states:
                cores_in_state[
                    (core_info.x, core_info.y, core_info.p)] = core_info
        elif core_info.state == states:
            cores_in_state[
                (core_info.x, core_info.y, core_info.p)] = core_info

    return cores_in_state


def get_cores_not_in_state(all_core_subsets, states, txrx):
    """

    :param all_core_subsets:
    :param states:
    :param txrx:
    :return:
    """
    core_infos = txrx.get_cpu_information(all_core_subsets)
    cores_not_in_state = OrderedDict()
    for core_info in core_infos:
        if hasattr(states, "__iter__"):
            if core_info.state not in states:
                cores_not_in_state[
                    (core_info.x, core_info.y, core_info.p)] = core_info
        elif core_info.state != states:
            cores_not_in_state[
                (core_info.x, core_info.y, core_info.p)] = core_info
    return cores_not_in_state


def get_core_status_string(core_infos):
    """ Get a string indicating the status of the given cores
    """
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


def get_core_subsets(core_infos):
    """ Convert core information from get_cores_in_state to core_subset objects
    """
    core_subsets = CoreSubsets()
    for (x, y, p) in core_infos:
        core_subsets.add_processor(x, y, p)
    return core_subsets


def sort_out_downed_chips_cores(downed_chips, downed_cores):
    """ Translate the down cores and down chips string into a form that \
        spinnman can understand

    :param downed_cores: string representing down cores
    :type downed_cores: str
    :param downed_chips: string representing down chips
    :type: downed_chips: str
    :return: a list of down cores and down chips in processor and \
            core subset format
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


def wait_for_cores_to_be_ready(executable_targets, app_id, txrx, sync_state):
    """

    :param executable_targets: the mapping between cores and binaries
    :param app_id: the app id that being used by the simulation
    :param txrx: the python interface to the spinnaker machine
    :param sync_state: The expected state once the applications are ready
    :return:
    """

    total_processors = executable_targets.total_processors
    all_core_subsets = executable_targets.all_core_subsets

    # check that everything has gone though c main
    processor_c_main = txrx.get_core_state_count(app_id, CPUState.C_MAIN)
    while processor_c_main != 0:
        time.sleep(0.1)
        processor_c_main = txrx.get_core_state_count(
            app_id, CPUState.C_MAIN)

    # check that the right number of processors are in sync state
    processors_ready = txrx.get_core_state_count(
        app_id, sync_state)
    if processors_ready != total_processors:
        unsuccessful_cores = get_cores_not_in_state(
            all_core_subsets, sync_state, txrx)

        # last chance to slip out of error check
        if len(unsuccessful_cores) != 0:
            break_down = get_core_status_string(
                unsuccessful_cores)
            raise exceptions.ExecutableFailedToStartException(
                "Only {} processors out of {} have successfully reached "
                "{}:{}".format(
                    processors_ready, total_processors, sync_state.name,
                    break_down),
                get_core_subsets(unsuccessful_cores))


def get_executables_by_run_type(
        executable_targets, placements, graph_mapper, type_to_find):
    """ Get executables by the type of the vertices
    """

    # Divide executables by type
    matching_executables = ExecutableTargets()
    other_executables = ExecutableTargets()
    for binary in executable_targets.binaries:
        core_subsets = executable_targets.get_cores_for_binary(binary)
        for core_subset in core_subsets:
            for p in core_subset.processor_ids:
                vertex = placements.get_vertex_on_processor(
                    core_subset.x, core_subset.y, p)
                is_of_type = False
                if isinstance(vertex, type_to_find):
                    matching_executables.add_processor(
                        binary, core_subset.x, core_subset.y, p)
                    is_of_type = True
                elif graph_mapper is not None:
                    assoc_vertex = graph_mapper.get_application_vertex(vertex)
                    if isinstance(assoc_vertex, type_to_find):
                        matching_executables.add_processor(
                            binary, core_subset.x, core_subset.y, p)
                        is_of_type = True
                if not is_of_type:
                    other_executables.add_processor(
                        binary, core_subset.x, core_subset.y, p)
    return matching_executables, other_executables
