import os
import logging
import struct

from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinn_utilities.log import FormatAdapter
from spinn_machine import CoreSubsets
from spinnman.model.enums import CPUState
from data_specification import utility_calls
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.utility_objs import ExecutableType

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

    :param vertices: the vertices to convert to core subsets
    :param placements: the placements object
    :return: the CoreSubSets of the vertices
    """
    core_subsets = CoreSubsets()
    for vertex in vertices:
        placement = placements.get_placement_of_vertex(vertex)
        core_subsets.add_processor(placement.x, placement.y, placement.p)
    return core_subsets


def find_executable_start_type(machine_vertex, graph_mapper=None):
    has_binary = isinstance(machine_vertex, AbstractHasAssociatedBinary)

    if not has_binary:
        return None
    elif graph_mapper is not None:
        app_vertex = graph_mapper.get_application_vertex(machine_vertex)
        if isinstance(app_vertex, AbstractHasAssociatedBinary):
            return app_vertex.get_binary_start_type()
    else:
        return machine_vertex.get_binary_start_type()
