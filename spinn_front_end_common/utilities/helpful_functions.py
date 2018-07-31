# dsg imports
from data_specification import utility_calls

# front end common imports
from spinn_front_end_common.utilities.exceptions import ConfigurationException

# SpiNMachine imports
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_machine import CoreSubsets

# general imports
import os
import logging
import struct
import datetime
import shutil

from spinnman.model.enums import CPUState
from spinn_utilities.log import FormatAdapter

logger = FormatAdapter(logging.getLogger(__name__))
APP_DIRNAME = 'application_generated_data_files'
FINISHED_FILENAME = "finished"
REPORTS_DIRNAME = "reports"
TIMESTAMP_FILENAME = "time_stamp"
_ONE_WORD = struct.Struct("<I")


def locate_extra_monitor_mc_receiver(
        machine, placement_x, placement_y,
        extra_monitor_cores_to_ethernet_connection_map):
    chip = machine.get_chip_at(placement_x, placement_y)
    return extra_monitor_cores_to_ethernet_connection_map[
        chip.nearest_ethernet_x, chip.nearest_ethernet_y]


def read_data(x, y, address, length, data_format, transceiver):
    """ Reads and converts a single data item from memory

    :param x: chip x
    :param y: chip y
    :param address: base address of the SDRAM chip to read
    :param length: length to read
    :param data_format: the format to read memory
    :param transceiver: the SpinnMan interface
    """
    # pylint: disable=too-many-arguments

    data = transceiver.read_memory(x, y, address, length)
    return struct.unpack_from(data_format, data)[0]


def write_address_to_user0(txrx, x, y, p, address):
    """ Writes the given address into the user_0 register of the given core.

    :param txrx: The transceiver.
    :param x: Chip coordinate.
    :param y: Chip coordinate.
    :param p: Core ID on chip.
    :param address: Value to write (32-bit integer)
    """
    user_0_address = txrx.get_user_0_register_address_from_core(p)
    txrx.write_memory(x, y, user_0_address, _ONE_WORD.pack(address))


def locate_memory_region_for_placement(placement, region, transceiver):
    """ Get the address of a region for a placement

    :param region: the region to locate the base address of
    :type region: int
    :param placement: the placement object to get the region address of
    :type placement: pacman.model.placements.Placement
    :param transceiver: the python interface to the SpiNNaker machine
    :type transceiver: spiNNMan.transciever.Transciever
    """
    regions_base_address = transceiver.get_cpu_information_from_core(
        placement.x, placement.y, placement.p).user[0]

    # Get the position of the region in the pointer table
    region_offset = utility_calls.get_region_base_address_offset(
        regions_base_address, region)

    # Get the actual address of the region
    region_address = transceiver.read_memory(
        placement.x, placement.y, region_offset, 4)
    return _ONE_WORD.unpack_from(region_address)[0]


def child_folder(parent, child_name):
    child = os.path.join(parent, child_name)
    if not os.path.exists(child):
        os.makedirs(child)
    return child


def set_up_output_application_data_specifics(
        where_to_write_application_data_files,
        max_application_binaries_kept, n_calls_to_run,
        this_run_time_string):
    """
    :param where_to_write_application_data_files:\
        the location where all app data is by default written to, or DEFAULT
    :type where_to_write_application_data_files: str
    :param max_application_binaries_kept:\
        The max number of report folders to keep active at any one time
    :type max_application_binaries_kept: int
    :param n_calls_to_run: the counter of how many times run has been called.
    :type n_calls_to_run: int
    :param this_run_time_string: the time stamp string for this run
    :type this_run_time_string: str
    :return: the run folder for this simulation to hold app data
    """
    if where_to_write_application_data_files == "DEFAULT":
        where_to_write_application_data_files = os.getcwd()
    application_generated_data_file_folder = child_folder(
        where_to_write_application_data_files, APP_DIRNAME)
    # add time stamped folder for this run
    this_run_time_folder = child_folder(
        application_generated_data_file_folder, this_run_time_string)

    # remove folders that are old and above the limit
    _remove_excess_folders(
        max_application_binaries_kept,
        application_generated_data_file_folder)

    # store timestamp in latest/time_stamp
    time_of_run_file_name = os.path.join(
        this_run_time_folder, TIMESTAMP_FILENAME)
    with open(time_of_run_file_name, "w") as f:
        f.writelines(str(this_run_time_string))

    # create sub folder within reports for sub runs (where changes need to be
    # recorded)
    this_run_time_sub_folder = child_folder(
        this_run_time_folder, "run_{}".format(n_calls_to_run))

    return this_run_time_sub_folder, this_run_time_folder


def set_up_report_specifics(
        default_report_file_path, max_reports_kept, n_calls_to_run,
        this_run_time_string=None):
    """
    :param default_report_file_path: The location where all reports reside
    :type default_report_file_path: str
    :param max_reports_kept:\
        The max number of report folders to keep active at any one time
    :type max_reports_kept: int
    :param n_calls_to_run: the counter of how many times run has been called.
    :type n_calls_to_run: int
    :param this_run_time_string: holder for the timestamp for future runs
    :type this_run_time_string: str
    :return: The folder for this run, the time_stamp
    """

    # determine common report folder
    config_param = default_report_file_path
    if config_param == "DEFAULT":
        directory = os.getcwd()

        # global reports folder
        report_default_directory = child_folder(directory, REPORTS_DIRNAME)
    elif config_param == "REPORTS":
        report_default_directory = REPORTS_DIRNAME
        if not os.path.exists(report_default_directory):
            os.makedirs(report_default_directory)
    else:
        report_default_directory = child_folder(config_param, REPORTS_DIRNAME)

    # clear and clean out folders considered not useful anymore
    if os.listdir(report_default_directory):
        _remove_excess_folders(max_reports_kept, report_default_directory)

    # determine the time slot for later
    if this_run_time_string is None:
        now = datetime.datetime.now()
        this_run_time_string = (
            "{:04}-{:02}-{:02}-{:02}-{:02}-{:02}-{:02}".format(
                now.year, now.month, now.day,
                now.hour, now.minute, now.second, now.microsecond))

    # handle timing app folder and cleaning of report folder from last run
    app_folder_name = child_folder(
        report_default_directory, this_run_time_string)

    # create sub folder within reports for sub runs (where changes need to be
    # recorded)
    app_sub_folder_name = child_folder(
        app_folder_name, "run_{}".format(n_calls_to_run))

    # store timestamp in latest/time_stamp for provenance reasons
    time_of_run_file_name = os.path.join(app_folder_name, TIMESTAMP_FILENAME)
    with open(time_of_run_file_name, "w") as f:
        f.writelines(this_run_time_string)
    return app_sub_folder_name, app_folder_name, this_run_time_string


def write_finished_file(app_data_runtime_folder, report_default_directory):
    # write a finished file that allows file removal to only remove folders
    # that are finished
    app_file_name = os.path.join(app_data_runtime_folder, FINISHED_FILENAME)
    with open(app_file_name, "w") as f:
        f.writelines("finished")

    app_file_name = os.path.join(report_default_directory, FINISHED_FILENAME)
    with open(app_file_name, "w") as f:
        f.writelines("finished")


def _remove_excess_folders(max_to_keep, starting_directory):
    files_in_report_folder = os.listdir(starting_directory)

    # while there's more than the valid max, remove the oldest one
    if len(files_in_report_folder) > max_to_keep:

        # sort files into time frame
        files_in_report_folder.sort(
            key=lambda temp_file:
            os.path.getmtime(os.path.join(starting_directory, temp_file)))

        # remove only the number of files required, and only if they have
        # the finished flag file created
        num_files_to_remove = len(files_in_report_folder) - max_to_keep
        files_removed = 0
        files_not_closed = 0
        for current_oldest_file in files_in_report_folder:
            finished_flag = os.path.join(os.path.join(
                starting_directory, current_oldest_file), FINISHED_FILENAME)
            if os.path.exists(finished_flag):
                shutil.rmtree(
                    os.path.join(starting_directory, current_oldest_file),
                    ignore_errors=True)
                files_removed += 1
            else:
                files_not_closed += 1
            if files_removed + files_not_closed >= num_files_to_remove:
                break
        if files_not_closed > max_to_keep // 4:
            logger.warning("{} has {} old reports that have not been closed",
                           starting_directory, files_not_closed)


def convert_string_into_chip_and_core_subset(cores):
    """ Translate a string list of cores into a core subset

    :param cores:\
        string representing down cores formatted as x,y,p[:x,y,p]*
    :type cores: str or None
    """
    ignored_cores = CoreSubsets()
    if cores is not None and cores != "None":
        for downed_core in cores.split(":"):
            x, y, processor_id = downed_core.split(",")
            ignored_cores.add_processor(int(x), int(y), int(processor_id))
    return ignored_cores


def sort_out_downed_chips_cores_links(
        downed_chips, downed_cores, downed_links):
    """ Translate the down cores and down chips string into a form that \
        spinnman can understand

    :param downed_cores:\
        string representing down cores formatted as x,y,p[:x,y,p]*
    :type downed_cores: str or None
    :param downed_chips:\
        string representing down chips formatted as x,y[:x,y]*
    :type downed_chips: str or None
    :param downed_links:\
        string representing down links formatted as x,y,link[:x,y,link]*
    :return:\
        a tuple of (\
            set of (x, y) of down chips, \
            set of (x, y, p) of down cores, \
            set of ((x, y), link ID) of down links)
    :rtype: (set((int, int)), set((int, int, int)), set(((int, int), int)))
    """
    ignored_chips = set()
    if downed_chips is not None and downed_chips != "None":
        for downed_chip in downed_chips.split(":"):
            x, y = downed_chip.split(",")
            ignored_chips.add((int(x), int(y)))

    ignored_cores = set()
    if downed_cores is not None and downed_cores != "None":
        for downed_core in downed_cores.split(":"):
            x, y, processor_id = downed_core.split(",")
            ignored_cores.add((int(x), int(y), int(processor_id)))

    ignored_links = set()
    if downed_links is not None and downed_links != "None":
        for downed_link in downed_links.split(":"):
            x, y, link_id = downed_link.split(",")
            ignored_links.add((int(x), int(y), int(link_id)))
    return ignored_chips, ignored_cores, ignored_links


def translate_iobuf_extraction_elements(
        hard_coded_cores, hard_coded_model_binary, executable_targets,
        executable_finder):
    """
    :param hard_coded_cores: list of cores to read iobuf from
    :param hard_coded_model_binary: list of binary names to read iobuf from
    :param executable_targets: the targets of cores and executable binaries
    :param executable_finder: where to find binaries paths from binary names
    :return: core subsets for the cores to read iobuf from
    """
    # all the cores
    if hard_coded_cores == "ALL" and hard_coded_model_binary == "None":
        return executable_targets.all_core_subsets

    # some hard coded cores
    if hard_coded_cores != "None" and hard_coded_model_binary == "None":
        ignored_cores = convert_string_into_chip_and_core_subset(
            hard_coded_cores)
        return ignored_cores

    # some binaries
    if hard_coded_cores == "None" and hard_coded_model_binary != "None":
        return _handle_model_binaries(
            hard_coded_model_binary, executable_targets, executable_finder)

    # nothing
    if hard_coded_cores == "None" and hard_coded_model_binary == "None":
        return CoreSubsets()

    # bit of both
    if hard_coded_cores != "None" and hard_coded_model_binary != "None":
        model_core_subsets = _handle_model_binaries(
            hard_coded_model_binary, executable_targets, executable_finder)
        hard_coded_core_core_subsets = \
            convert_string_into_chip_and_core_subset(hard_coded_cores)
        for core_subset in hard_coded_core_core_subsets:
            model_core_subsets.add_core_subset(core_subset)
        return model_core_subsets

    # should never get here,
    raise ConfigurationException("Something odd has happened")


def _handle_model_binaries(
        hard_coded_model_binary, executable_targets, executable_finder):
    """
    :param hard_coded_model_binary: list of binary names to read iobuf from
    :param executable_targets: the targets of cores and executable binaries
    :param executable_finder: where to find binaries paths from binary names
    :return: core subsets from binaries that need iobuf to be read from them
    """
    model_binaries = hard_coded_model_binary.split(",")
    cores = CoreSubsets()
    for model_binary in model_binaries:
        model_binary_path = \
            executable_finder.get_executable_path(model_binary)
        core_subsets = \
            executable_targets.get_cores_for_binary(model_binary_path)
        for core_subset in core_subsets:
            cores.add_core_subset(core_subset)
    return cores


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


_BOOLEAN_STATES = {
    'true': True, '1': True, 'on': True, 'yes': True,
    'false': False, '0': False, 'off': False, 'no': False}


def read_config_boolean(config, section, item):
    """ Get the boolean value of a config item, returning None if the value\
        is "None"
    """
    value = read_config(config, section, item)
    if value is None:
        return value
    if value.lower() in _BOOLEAN_STATES:
        return _BOOLEAN_STATES[value.lower()]
    raise ValueError("Unknown boolean value {} in configuration {}:{}".format(
        value, section, item))


def generate_unique_folder_name(folder, filename, extension):
    """ Generate a unique file name with a given extension in a given folder

    :param folder: where to put this unique file
    :param filename: the name of the first part of the file without extension
    :param extension: extension of the file
    :return: file path with a unique addition
    """
    new_file_path = os.path.join(folder, "{}{}".format(filename, extension))
    count = 2
    while os.path.exists(new_file_path):
        new_file_path = os.path.join(
            folder, "{}_{}{}".format(filename, count, extension))
        count += 1
    return new_file_path


def get_ethernet_chip(machine, board_address):
    """ Locate the chip with the given board IP address

    :param machine: the SpiNNaker machine
    :param board_address: the board address to locate the chip of.
    :return: The chip that supports that board address
    :raises ConfigurationException:\
        when that board address has no chip associated with it
    """
    for chip in machine.ethernet_connected_chips:
        if chip.ip_address == board_address:
            return chip
    raise ConfigurationException(
        "cannot find the Ethernet connected chip with the board address {}"
        .format(board_address))


def convert_time_diff_to_total_milliseconds(sample):
    """ Convert between a time diff and total milliseconds.

    :return: total milliseconds
    :rtype: float
    """
    return (sample.total_seconds() * 1000.0) + (sample.microseconds / 1000.0)


def determine_flow_states(executable_types, no_sync_changes):
    """ Get the start and end states for these executable types.

    :param executable_types: \
        the execute types to locate start and end states from
    :type executable_types: dict(\
        :py:class:`spinn_front_end_common.utilities.utility_objs.executable_type.ExecutableType`\
        -> any)
    :param no_sync_changes: the number of times sync signals been sent
    :type no_sync_changes: int
    :return: dict of executable type to states.
    :rtype: 2-tuple
    """
    expected_start_states = dict()
    expected_end_states = dict()
    for start_type in executable_types.keys():

        # cores that ignore all control and are just running
        if start_type == ExecutableType.RUNNING:
            expected_start_states[ExecutableType.RUNNING] = [
                CPUState.RUNNING, CPUState.FINISHED]
            expected_end_states[ExecutableType.RUNNING] = [
                CPUState.RUNNING, CPUState.FINISHED]

        # cores that require a sync barrier
        elif start_type == ExecutableType.SYNC:
            expected_start_states[ExecutableType.SYNC] = [CPUState.SYNC0]
            expected_end_states[ExecutableType.SYNC] = [CPUState.FINISHED]

        # cores that use our sim interface
        elif start_type == ExecutableType.USES_SIMULATION_INTERFACE:
            if no_sync_changes % 2 == 0:
                expected_start_states[start_type] = [CPUState.SYNC0]
            else:
                expected_start_states[start_type] = [CPUState.SYNC1]
            expected_end_states[start_type] = [CPUState.PAUSED]

    # if no states, go boom.
    if not expected_start_states:
        raise ConfigurationException(
            "Unknown executable start types {}".format(executable_types))
    return expected_start_states, expected_end_states


def convert_vertices_to_core_subset(vertices, placements):
    """ Converts vertices into core subsets.

    :param extra_monitor_cores_to_set:\
        the vertices to convert to core subsets
    :param placements: the placements object
    :return: the CoreSubSets of the vertices
    """
    core_subsets = CoreSubsets()
    for vertex in vertices:
        placement = placements.get_placement_of_vertex(vertex)
        core_subsets.add_processor(placement.x, placement.y, placement.p)
    return core_subsets
