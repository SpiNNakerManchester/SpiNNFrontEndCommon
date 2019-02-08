import os
import logging
import struct
import datetime
import shutil
import math
from spinn_utilities.log import FormatAdapter
from spinn_machine import CoreSubsets
from spinnman.model.enums import CPUState
from data_specification import utility_calls
from pacman.model.constraints.key_allocator_constraints import (
    AbstractKeyAllocatorConstraint, FixedKeyAndMaskConstraint)
from pacman.model.graphs.common import EdgeTrafficType
from pacman.utilities.algorithm_utilities import ElementAllocatorAlgorithm
from pacman.model.routing_info.base_key_and_mask import BaseKeyAndMask
from pacman.utilities.algorithm_utilities.routing_info_allocator_utilities \
    import generate_key_ranges_from_mask
from pacman.utilities.utility_calls import locate_constraints_of_type
from spinn_front_end_common.abstract_models import (
    AbstractProvidesIncomingPartitionConstraints)
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.utility_objs import ExecutableType

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
    """ Convert between a time difference and total milliseconds.

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

        # cores that use our simulation interface
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


def produce_key_constraint_based_off_outgoing_partitions(
        machine_graph, vertex, mask, virtual_key, partition):
    """ supports vertices which can support their destinations enforcing
    their key space.

    :param machine_graph: the machine graph
    :param vertex: the source vertex (usually a retina or RIPMCS)
    :param mask: the mask the source expects to transmit with
    :param virtual_key: the key the source expects to transmit with
    :param partition: the edge partition to process
    :return: the constraints the source vertex should use.
    """
    if virtual_key is not None:
        if len(partition.constraints) == 0:
            keys_covered, has_tried_to_cover, key_space =  \
                _verify_if_incoming_constraints_covers_key_space(
                    machine_graph=machine_graph, vertex=vertex,
                    mask=mask, virtual_key=virtual_key)
            if not keys_covered and not has_tried_to_cover:
                return list([FixedKeyAndMaskConstraint(
                    [BaseKeyAndMask(virtual_key, mask)])])
            elif not keys_covered and has_tried_to_cover:
                key_message = ""
                for element_space in key_space:
                    mask, _ = calculate_mask(element_space.size)
                    key_message += "[start key:{} and mask {}] ".format(
                        element_space.start_address, mask)
                raise ConfigurationException(
                    "the retina key space has not been covered correctly. "
                    "and so packets will fly uncontrolled. please insert a "
                    "vertex that covers the following key spaces: {}".format(
                        key_message))
    return list()


def _verify_if_incoming_constraints_covers_key_space(
        machine_graph, vertex, virtual_key, mask):
    """ checks the partitions going out of the vertex and sees if there's
    constraints that cover of try to cover the key space of the vertex.

    :param machine_graph: the machine graph
    :param vertex: the vertex to worry about
    :param virtual_key: the key that vertex is to transmit with
    :param mask: the mask of the key that the vertex will transmit with
    :return: 2 Booleans, first saying if the key space is covered, the second\
            saying if the key space was attempted to be covered.
    """
    tried_to_cover = False
    key_space = ElementAllocatorAlgorithm(
        list(generate_key_ranges_from_mask(virtual_key, mask)))
    outgoing_partitions = \
        machine_graph.get_outgoing_edge_partitions_starting_at_vertex(vertex)
    for outgoing_partition in outgoing_partitions:
        if outgoing_partition.traffic_type == EdgeTrafficType.MULTICAST:
            tried_to_cover = _process_multicast_partition(
                outgoing_partition, key_space, tried_to_cover)
    if key_space.space_remaining() != 0:
        return False, tried_to_cover, key_space.spaces_left()
    return True, tried_to_cover, key_space.spaces_left()


def calculate_mask(n_keys):
    if n_keys == 1:
        return 0xFFFFFFFF, 1
    temp_value = int(math.ceil(math.log(n_keys, 2)))
    max_key = (int(math.pow(2, temp_value)) - 1)
    mask = 0xFFFFFFFF - max_key
    return mask, max_key


def _process_multicast_partition(
        outgoing_partition, key_space, tried_to_cover):
    for edge in outgoing_partition.edges:
        if isinstance(
                edge.post_vertex,
                AbstractProvidesIncomingPartitionConstraints):
            constraints = edge.post_vertex.\
                get_incoming_partition_constraints(outgoing_partition)
            key_constraints = locate_constraints_of_type(
                constraints, AbstractKeyAllocatorConstraint)
            if len(key_constraints) > 1:
                raise ConfigurationException(
                    "There are too many key constraints. Please rectify "
                    "and try again")
            key_constraint = key_constraints[0]
            if isinstance(key_constraint, FixedKeyAndMaskConstraint):
                keys_and_masks = key_constraint.keys_and_masks
                for key_and_mask in keys_and_masks:
                    for base_key, n_keys in generate_key_ranges_from_mask(
                            key_and_mask.key, key_and_mask.mask):
                        key_space.allocate_elements(base_key, n_keys)
                    tried_to_cover = True
    return tried_to_cover
