# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import logging
import struct
from spinn_utilities.log import FormatAdapter
from spinn_machine import CoreSubsets
from spinnman.model.enums import CPUState
from data_specification import utility_calls
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from .constants import MICRO_TO_MILLISECOND_CONVERSION

logger = FormatAdapter(logging.getLogger(__name__))
_n_word_structs = []


def locate_extra_monitor_mc_receiver(
        machine, placement_x, placement_y,
        packet_gather_cores_to_ethernet_connection_map):
    """ Get the data speed up gatherer that can be used to talk to a\
        particular chip. This will be on the same board.

    :param ~spinn_machine.Machine machine: The machine descriptor
    :param int placement_x: The X coordinate of the reference chip
    :param int placement_y: The Y coordinate of the reference chip
    :param packet_gather_cores_to_ethernet_connection_map:
    :type packet_gather_cores_to_ethernet_connection_map:
        dict(tuple(int,int), DataSpeedUpPacketGatherMachineVertex)
    :rtype: DataSpeedUpPacketGatherMachineVertex
    """
    chip = machine.get_chip_at(placement_x, placement_y)
    return packet_gather_cores_to_ethernet_connection_map[
        chip.nearest_ethernet_x, chip.nearest_ethernet_y]


def read_data(x, y, address, length, data_format, transceiver):
    """ Reads and converts a single data item from memory.

    :param int x: chip x
    :param int y: chip y
    :param int address: base address of the SDRAM chip to read
    :param int length: length to read
    :param str data_format:
        the format to read memory (see :py:func:`struct.pack`)
    :param ~spinnman.transceiver.Transceiver transceiver:
        the SpinnMan interface
    """
    # pylint: disable=too-many-arguments

    data = transceiver.read_memory(x, y, address, length)
    return struct.unpack_from(data_format, data)[0]


def write_address_to_user0(txrx, x, y, p, address):
    """ Writes the given address into the user_0 register of the given core.

    :param ~spinnman.transceiver.Transceiver txrx: The transceiver.
    :param int x: Chip coordinate.
    :param int y: Chip coordinate.
    :param int p: Core ID on chip.
    :param int address: Value to write (32-bit integer)
    """
    user_0_address = txrx.get_user_0_register_address_from_core(p)
    txrx.write_memory(x, y, user_0_address, address)


def locate_memory_region_for_placement(placement, region, transceiver):
    """ Get the address of a region for a placement.

    :param int region: the region to locate the base address of
    :param ~pacman.model.placements.Placement placement:
        the placement object to get the region address of
    :param ~spinnman.transceiver.Transceiver transceiver:
        the python interface to the SpiNNaker machine
    :return: the address
    :rtype: int
    """
    regions_base_address = transceiver.get_cpu_information_from_core(
        placement.x, placement.y, placement.p).user[0]

    # Get the position of the region in the pointer table
    region_offset = utility_calls.get_region_base_address_offset(
        regions_base_address, region)

    # Get the actual address of the region
    return transceiver.read_word(placement.x, placement.y, region_offset)


def convert_string_into_chip_and_core_subset(cores):
    """ Translate a string list of cores into a core subset

    :param cores:
        string representing down cores formatted as x,y,p[:x,y,p]*
    :type cores: str or None
    :rtype: ~spinn_machine.CoreSubsets
    """
    ignored_cores = CoreSubsets()
    if cores is not None and cores != "None":
        for downed_core in cores.split(":"):
            x, y, processor_id = downed_core.split(",")
            ignored_cores.add_processor(int(x), int(y), int(processor_id))
    return ignored_cores


def flood_fill_binary_to_spinnaker(executable_targets, binary, txrx, app_id):
    """ Flood fills a binary to spinnaker on a given `app_id` \
        given the executable targets and binary.

    :param ~spinnman.model.ExecutableTargets executable_targets:
        the executable targets object
    :param str binary: the (name of the) binary to flood fill
    :param ~spinnman.transceiver.Transceiver txrx: spinnman instance
    :param int app_id: the application ID to load it as
    :return: the number of cores it was loaded onto
    :rtype: int
    """
    core_subset = executable_targets.get_cores_for_binary(binary)
    txrx.execute_flood(
        core_subset, binary, app_id, wait=True, is_filename=True)
    return len(core_subset)


def read_config(config, section, item):
    """ Get the string value of a config item, returning None if the value\
        is "None"

    :param ~configparser.ConfigParser config:
        The configuration to look things up in.
    :param str section: The section name
    :param str item: The item name.
    :rtype: str or None
    """
    value = config.get(section, item)
    if value == "None":
        return None
    return value


def read_config_int(config, section, item):
    """ Get the integer value of a config item, returning None if the value\
        is "None"

    :param ~configparser.ConfigParser config:
        The configuration to look things up in.
    :param str section: The section name
    :param str item: The item name.
    :rtype: int or None
    """
    value = read_config(config, section, item)
    if value is None:
        return value
    return int(value)


def read_config_float(config, section, item):
    """ Get the float value of a config item, returning None if the value\
        is "None"

    :param ~configparser.ConfigParser config:
        The configuration to look things up in.
    :param str section: The section name
    :param str item: The item name.
    :rtype: float or None
    """
    value = read_config(config, section, item)
    if value is None:
        return value
    return float(value)


_BOOLEAN_STATES = {
    'true': True, '1': True, 'on': True, 'yes': True,
    'false': False, '0': False, 'off': False, 'no': False}


def read_config_boolean(config, section, item):
    """ Get the boolean value of a config item, returning None if the value\
        is "None"

    :param ~configparser.ConfigParser config:
        The configuration to look things up in.
    :param str section: The section name
    :param str item: The item name.
    :rtype: bool or None
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

    :param str folder: where to put this unique file
    :param str filename:
        the name of the first part of the file without extension
    :param str extension: extension of the file
    :return: file path with a unique addition
    :rtype: str
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

    :param ~spinn_machine.Machine machine: the SpiNNaker machine
    :param str board_address: the board address to locate the chip of.
    :return: The chip that supports that board address
    :rtype: ~spinn_machine.Chip
    :raises ConfigurationException:
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

    :param ~datetime.timedelta sample:
    :return: total milliseconds
    :rtype: float
    """
    return ((sample.total_seconds() * MICRO_TO_MILLISECOND_CONVERSION) +
            (sample.microseconds / MICRO_TO_MILLISECOND_CONVERSION))


def determine_flow_states(executable_types, no_sync_changes):
    """ Get the start and end states for these executable types.

    :param dict(ExecutableType,any) executable_types:
        the execute types to locate start and end states from
    :param int no_sync_changes: the number of times sync signals been sent
    :return: dict of executable type to states.
    :rtype: tuple(dict(ExecutableType,~spinnman.model.enums.CPUState),
        dict(ExecutableType,~spinnman.model.enums.CPUState))
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

    :param iterable(~pacman.model.graphs.machine.MachineVertex) vertices:
        the vertices to convert to core subsets
    :param ~pacman.model.placements.Placements placements:
        the placements object
    :return: the CoreSubSets of the vertices
    :rtype: ~spinn_machine.CoreSubsets
    """
    core_subsets = CoreSubsets()
    for vertex in vertices:
        placement = placements.get_placement_of_vertex(vertex)
        core_subsets.add_processor(placement.x, placement.y, placement.p)
    return core_subsets


def n_word_struct(n_words):
    """ Manages a precompiled cache of structs for parsing blocks of words. \
        Thus, this::

        data = n_word_struct(n_words).unpack(data_blob)

    Is much like doing this::

        data = struct.unpack("<{}I".format(n_words), data_blob)

    except quite a bit more efficient because things are shared including the
    cost of parsing the format.

    :param int n_words: The number of *SpiNNaker words* to be handled.
    :return: A struct for working with that many words.
    :rtype: ~struct.Struct
    """
    global _n_word_structs
    while len(_n_word_structs) < n_words + 1:
        _n_word_structs += [None] * (n_words + 1 - len(_n_word_structs))
    s = _n_word_structs[n_words]
    if s is not None:
        return s
    new_struct = struct.Struct("<{}I".format(n_words))
    _n_word_structs[n_words] = new_struct
    return new_struct


def get_defaultable_source_id(entry):
    """ Hack to support the source requirement for the router compressor\
        on chip.

    :param ~spinn_machine.MulticastRoutingEntry entry:
        the multicast router table entry.
    :return: return the source value
    :rtype: int
    """
    if entry.defaultable:
        return (list(entry.link_ids)[0] + 3) % 6
    elif entry.link_ids:
        return list(entry.link_ids)[0]
    return 0
