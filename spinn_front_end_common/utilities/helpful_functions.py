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
FINISHED_FILENAME = "finished"


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
        max_application_binaries_kept, app_id, n_calls_to_run,
        this_run_time_string):
    """

    :param where_to_write_application_data_files:\
        the location where all app data is by default written to
    :param max_application_binaries_kept:\
        The max number of report folders to keep active at any one time
    :param app_id:\
        the id used for identifying the simulation on the SpiNNaker machine
    :param n_calls_to_run: the counter of how many times run has been called.
    :param this_run_time_string: the time stamp string for this run
    :return: the run folder for this simulation to hold app data
    """
    this_run_time_folder = None
    if where_to_write_application_data_files == "DEFAULT":
        directory = os.getcwd()
        application_generated_data_file_folder = \
            os.path.join(directory, 'application_generated_data_files')
        if not os.path.exists(application_generated_data_file_folder):
            os.makedirs(application_generated_data_file_folder)

        _remove_excess_folders(
            max_application_binaries_kept,
            application_generated_data_file_folder)

        # add time stamped folder for this run
        this_run_time_folder = \
            os.path.join(
                application_generated_data_file_folder, this_run_time_string)
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
            os.path.join(where_to_write_application_data_files,
                         this_run_time_string)
        if not os.path.exists(this_run_time_folder):
            os.makedirs(this_run_time_folder)

        # remove folders that are old and above the limit
        _remove_excess_folders(
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

    # create sub folder within reports for sub runs (where changes need to be
    # recorded)
    this_run_time_sub_folder = os.path.join(
        this_run_time_folder, "run_{}".format(n_calls_to_run))

    if not os.path.exists(this_run_time_sub_folder):
        os.makedirs(this_run_time_sub_folder)

    return this_run_time_sub_folder, this_run_time_folder


def set_up_report_specifics(
        default_report_file_path, max_reports_kept, app_id, n_calls_to_run,
        this_run_time_string=None):
    """

    :param default_report_file_path: The location where all reports reside
    :param max_reports_kept:\
        The max number of report folders to keep active at any one time
    :param app_id:\
        the id used for identifying the simulation on the SpiNNaker machine
    :param n_calls_to_run: the counter of how many times run has been called.
    :param this_run_time_string: holder for the timestamp for future runs
    :return: The folder for this run, the time_stamp
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
    if not created_folder and len(os.listdir(report_default_directory)) > 0:
        _remove_excess_folders(max_reports_kept, report_default_directory)

    # determine the time slot for later
    if this_run_time_string is None:
        this_run_time = datetime.datetime.now()
        this_run_time_string = (
            "{:04}-{:02}-{:02}-{:02}-{:02}-{:02}-{:02}".format(
                this_run_time.year, this_run_time.month, this_run_time.day,
                this_run_time.hour, this_run_time.minute,
                this_run_time.second, this_run_time.microsecond))

    # handle timing app folder and cleaning of report folder from last run
    app_folder_name = os.path.join(
        report_default_directory, this_run_time_string)

    if not os.path.exists(app_folder_name):
            os.makedirs(app_folder_name)

    # create sub folder within reports for sub runs (where changes need to be
    # recorded)
    app_sub_folder_name = os.path.join(
        app_folder_name, "run_{}".format(n_calls_to_run))

    if not os.path.exists(app_sub_folder_name):
        os.makedirs(app_sub_folder_name)

    # store timestamp in latest/time_stamp for provenance reasons
    time_of_run_file_name = os.path.join(app_folder_name, "time_stamp")
    writer = open(time_of_run_file_name, "w")
    writer.writelines("app_{}_{}".format(app_id, this_run_time_string))
    writer.flush()
    writer.close()
    return app_sub_folder_name, app_folder_name, this_run_time_string


def write_finished_file(app_data_runtime_folder, report_default_directory):
    # write a finished file that allows file removal to only remove folders
    # that are finished
    app_file_name = os.path.join(app_data_runtime_folder, FINISHED_FILENAME)
    writer = open(app_file_name, "w")
    writer.writelines("finished")
    writer.flush()
    writer.close()

    app_file_name = os.path.join(report_default_directory, FINISHED_FILENAME)
    writer = open(app_file_name, "w")
    writer.writelines("finished")
    writer.flush()
    writer.close()


def _remove_excess_folders(max_to_keep, starting_directory):
    files_in_report_folder = os.listdir(starting_directory)

    # while there's more than the valid max, remove the oldest one
    if len(files_in_report_folder) > max_to_keep:

        # sort files into time frame
        files_in_report_folder.sort(
            cmp, key=lambda temp_file:
            os.path.getmtime(os.path.join(starting_directory,
                                          temp_file)))

        # remove only the number of files required, and only if they have
        # the finished flag file created
        num_files_to_remove = len(files_in_report_folder) - max_to_keep
        files_removed = 0
        for current_oldest_file in files_in_report_folder:
            finished_flag = os.path.join(os.path.join(
                starting_directory, current_oldest_file), FINISHED_FILENAME)
            if (os.path.exists(finished_flag) and
                    files_removed < num_files_to_remove):
                shutil.rmtree(os.path.join(starting_directory,
                                           current_oldest_file),
                              ignore_errors=True)
                files_removed += 1


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


def read_config(config, section, item):
    """ Get the string value of a config item, returning None if the value\
        is "None"
    """
    value = config.get(section, item)
    if value == "None":
        return None
    return value


def read_config_int(config, section, item):
    """ Get the integer value of a config item, returning None if the value\
        is "None"
    """
    value = read_config(config, section, item)
    if value is None:
        return value
    return int(value)


def read_config_boolean(config, section, item):
    """ Get the boolean value of a config item, returning None if the value\
        is "None"
    """
    value = read_config(config, section, item)
    if value is None:
        return value
    return bool(value)
