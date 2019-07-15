import os
import logging
import struct
from spinn_utilities.log import FormatAdapter
from spinn_machine import CoreSubsets
from spinnman.model.enums import CPUState
from data_specification import utility_calls
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.utility_objs import (
    ExecutableTargets, ExecutableType)
from .globals_variables import get_simulator
from spinnman.model.cpu_infos import CPUInfos

logger = FormatAdapter(logging.getLogger(__name__))
_ONE_WORD = struct.Struct("<I")


def locate_extra_monitor_mc_receiver(
        machine, placement_x, placement_y,
        packet_gather_cores_to_ethernet_connection_map):
    chip = machine.get_chip_at(placement_x, placement_y)
    return packet_gather_cores_to_ethernet_connection_map[
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
    :type placement: :py:class:`~pacman.model.placements.Placement`
    :param transceiver: the python interface to the SpiNNaker machine
    :type transceiver: :py:class:`~spinnman.Transceiver`
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
    :rtype: tuple(set(tuple(int, int)), set(tuple(int, int, int)),\
        set(tuple(tuple(int, int), int)))
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


def flood_fill_binary_to_spinnaker(executable_targets, binary, txrx, app_id):
    """ flood fills a binary to spinnaker on a given app_id \
    given the executable targets and binary.

    :param executable_targets: the executable targets object
    :param binary: the binary to flood fill
    :param txrx: spinnman instance
    :type txrx: :py:class:`~spinnman.Tranceiver`
    :param app_id: the app id to load it on
    :return: the number of cores it was loaded onto
    """
    core_subset = executable_targets.get_cores_for_binary(binary)
    txrx.execute_flood(
        core_subset, binary, app_id, wait=True, is_filename=True)
    return len(core_subset)


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
        :py:class:`~spinn_front_end_common.utilities.utility_objs.ExecutableType`\
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


def _emergency_state_check(txrx, app_id):
    # pylint: disable=broad-except
    try:
        rte_count = txrx.get_core_state_count(
            app_id, CPUState.RUN_TIME_EXCEPTION)
        watchdog_count = txrx.get_core_state_count(app_id, CPUState.WATCHDOG)
        if rte_count or watchdog_count:
            logger.warning(
                "unexpected core states (rte={}, wdog={})",
                txrx.get_cores_in_state(None, CPUState.RUN_TIME_EXCEPTION),
                txrx.get_cores_in_state(None, CPUState.WATCHDOG))
    except Exception:
        logger.exception(
            "Could not read the status count - going to individual cores")
        machine = txrx.get_machine_details()
        infos = CPUInfos()
        errors = list()
        for chip in machine.chips:
            for p in chip.processors:
                try:
                    info = txrx.get_cpu_information_from_core(
                        chip.x, chip.y, p)
                    if info.state in (
                            CPUState.RUN_TIME_EXCEPTION, CPUState.WATCHDOG):
                        infos.add_processor(chip.x, chip.y, p, info)
                except Exception:
                    errors.append((chip.x, chip.y, p))
        logger.warn(txrx.get_core_status_string(infos))
        logger.warn("Could not read information from cores {}".format(errors))


# TRICKY POINT: Have to delay the import to here because of import circularity
def _emergency_iobuf_extract(txrx, executable_targets):
    # pylint: disable=protected-access
    from spinn_front_end_common.interface.interface_functions import (
        ChipIOBufExtractor)
    sim = get_simulator()
    extractor = ChipIOBufExtractor(
        recovery_mode=True, filename_template="emergency_iobuf_{}_{}_{}.txt")
    extractor(txrx, executable_targets, sim._executable_finder,
              sim._provenance_file_path)


def emergency_recover_state_from_failure(txrx, app_id, vertex, placement):
    """ Used to get at least *some* information out of a core when something\
    goes badly wrong. Not a replacement for what abstract spinnaker base does.

    :param txrx: The transceiver.
    :param app_id: The ID of the application.
    :param vertex: The vertex to retrieve the IOBUF from if it is suspected\
        as being dead
    :type vertex: \
        :py:class:`spinn_front_end_common.abstract_models.AbstractHasAssociatedBinary`
    :param placement: Where the vertex is located.
    """
    # pylint: disable=protected-access
    _emergency_state_check(txrx, app_id)
    target = ExecutableTargets()
    path = get_simulator()._executable_finder.get_executable_path(
        vertex.get_binary_file_name())
    target.add_processor(
        path, placement.x, placement.y, placement.p,
        vertex.get_binary_start_type())
    _emergency_iobuf_extract(txrx, target)


def emergency_recover_states_from_failure(txrx, app_id, executable_targets):
    """ Used to get at least *some* information out of a core when something\
    goes badly wrong. Not a replacement for what abstract spinnaker base does.

    :param txrx: The transceiver.
    :param app_id: The ID of the application.
    :param executable_targets: The what/where mapping
    """
    _emergency_state_check(txrx, app_id)
    _emergency_iobuf_extract(txrx, executable_targets)
