# dsg imports
from data_specification import utility_calls

# front end common imports
from spinn_front_end_common.interface import interface_functions
from spinn_front_end_common.utilities import report_functions as \
    front_end_common_report_functions
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common import mapping_algorithms

# SpiNMachine imports
from spinn_machine.core_subsets import CoreSubsets

# general imports
import os
import datetime
import shutil
import logging
import re
import inspect
import struct
from ConfigParser import RawConfigParser

logger = logging.getLogger(__name__)
FINISHED_FILENAME = "finished"


def get_valid_components(module, terminator):
    """ Get possible components

    :param module:
    :param terminator:
    :rtype: dict
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
        max_application_binaries_kept, n_calls_to_run,
        this_run_time_string):
    """

    :param where_to_write_application_data_files:\
        the location where all app data is by default written to
    :param max_application_binaries_kept:\
        The max number of report folders to keep active at any one time
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
        writer.writelines("{}".format(this_run_time_string))
        writer.flush()
        writer.close()

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
        writer.writelines("{}".format(this_run_time_string))

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
        default_report_file_path, max_reports_kept, n_calls_to_run,
        this_run_time_string=None):
    """

    :param default_report_file_path: The location where all reports reside
    :param max_reports_kept:\
        The max number of report folders to keep active at any one time
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
    writer.writelines("{}".format(this_run_time_string))
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
        files_not_closed = 0
        for current_oldest_file in files_in_report_folder:
            finished_flag = os.path.join(os.path.join(
                starting_directory, current_oldest_file), FINISHED_FILENAME)
            if os.path.exists(finished_flag):
                shutil.rmtree(os.path.join(starting_directory,
                                           current_oldest_file),
                              ignore_errors=True)
                files_removed += 1
            else:
                files_not_closed += 1
            if (files_removed + files_not_closed) >= num_files_to_remove:
                break
        if files_not_closed > max_to_keep / 4:
            logger.warning("{} has {} old reports that have not been closed".
                           format(starting_directory, files_not_closed))


def get_front_end_common_pacman_xml_paths():
    """ Get the XML path for the front end common interface functions
    """
    return [
        os.path.join(
            os.path.dirname(interface_functions.__file__),
            "front_end_common_interface_functions.xml"),
        os.path.join(
            os.path.dirname(front_end_common_report_functions.__file__),
            "front_end_common_reports.xml"),
        os.path.join(
            os.path.dirname(mapping_algorithms.__file__),
            "front_end_common_mapping_algorithms.xml"
        )
    ]


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
            ignored_cores.add_processor((int(x), int(y), int(processor_id)))
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
            set of ((x, y), link id) of down links)
    :rtype: ({(int, int,), }, {(int, int, int), }, {((int, int), int), })
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
        _, ignored_cores = convert_string_into_chip_and_core_subset(
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
        _, hard_coded_core_core_subsets = \
            convert_string_into_chip_and_core_subset(hard_coded_cores)
        for core_subset in hard_coded_core_core_subsets:
            model_core_subsets.add_core_subset(core_subset)
        return model_core_subsets

    # should never get here,
    raise exceptions.ConfigurationException("Something odd has happened")


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


def read_config_boolean(config, section, item):
    """ Get the boolean value of a config item, returning None if the value\
        is "None"
    """
    value = read_config(config, section, item)
    if value is None:
        return value
    if value.lower() in RawConfigParser._boolean_states:
        return RawConfigParser._boolean_states[value.lower()]
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
