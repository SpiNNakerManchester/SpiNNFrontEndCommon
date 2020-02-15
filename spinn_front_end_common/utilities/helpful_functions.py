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

from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinn_utilities.log import FormatAdapter
from spinn_machine import CoreSubsets
from spinnman.model.enums import CPUState
from spinnman.model.cpu_infos import CPUInfos
from data_specification import utility_calls
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.utility_objs import (
    ExecutableTargets, ExecutableType)
from .globals_variables import get_simulator
from .constants import BYTES_PER_WORD

logger = FormatAdapter(logging.getLogger(__name__))
_ONE_WORD = struct.Struct("<I")


def locate_extra_monitor_mc_receiver(
        machine, placement_x, placement_y,
        packet_gather_cores_to_ethernet_connection_map):
    """
    :param machine: The machine descriptor
    :type machine: ~spinn_machine.Machine
    :param placement_x: The X coordinate of the reference chip
    :type placement_x: int
    :param placement_y: The Y coordinate of the reference chip
    :type placement_y: int
    :param packet_gather_cores_to_ethernet_connection_map:
    :type: dict(tuple(int,int),?)
    :rtype: ?
    """
    chip = machine.get_chip_at(placement_x, placement_y)
    return packet_gather_cores_to_ethernet_connection_map[
        chip.nearest_ethernet_x, chip.nearest_ethernet_y]


def read_data(x, y, address, length, data_format, transceiver):
    """ Reads and converts a single data item from memory

    :param x: chip x
    :type x: int
    :param y: chip y
    :type y: int
    :param address: base address of the SDRAM chip to read
    :type address: int
    :param length: length to read
    :type length: int
    :param data_format: the format to read memory (see `struct.pack`)
    :type data_format: str
    :param transceiver: the SpinnMan interface
    :type transceiver: ~spinnman.transceiver.Transceiver
    """
    # pylint: disable=too-many-arguments

    data = transceiver.read_memory(x, y, address, length)
    return struct.unpack_from(data_format, data)[0]


def write_address_to_user0(txrx, x, y, p, address):
    """ Writes the given address into the user_0 register of the given core.

    :param txrx: The transceiver.
    :type txrx: ~spinnman.transceiver.Transceiver
    :param x: Chip coordinate.
    :type x: int
    :param y: Chip coordinate.
    :type y: int
    :param p: Core ID on chip.
    :type p: int
    :param address: Value to write (32-bit integer)
    :type address: int
    """
    user_0_address = txrx.get_user_0_register_address_from_core(p)
    txrx.write_memory(x, y, user_0_address, _ONE_WORD.pack(address))


def locate_memory_region_for_placement(placement, region, transceiver):
    """ Get the address of a region for a placement

    :param region: the region to locate the base address of
    :type region: int
    :param placement: the placement object to get the region address of
    :type placement: ~pacman.model.placements.Placement
    :param transceiver: the python interface to the SpiNNaker machine
    :type transceiver: ~spinnman.transceiver.Transceiver
    """
    regions_base_address = transceiver.get_cpu_information_from_core(
        placement.x, placement.y, placement.p).user[0]

    # Get the position of the region in the pointer table
    region_offset = utility_calls.get_region_base_address_offset(
        regions_base_address, region)

    # Get the actual address of the region
    region_address = transceiver.read_memory(
        placement.x, placement.y, region_offset, BYTES_PER_WORD)
    return _ONE_WORD.unpack_from(region_address)[0]


def convert_string_into_chip_and_core_subset(cores):
    """ Translate a string list of cores into a core subset

    :param cores:\
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
    """ flood fills a binary to spinnaker on a given app_id \
    given the executable targets and binary.

    :param executable_targets: the executable targets object
    :type executable_targets: ExecutableTargets
    :param binary: the (name of the) binary to flood fill
    :type binary: str
    :param txrx: spinnman instance
    :type txrx: ~spinnman.transceiver.Transceiver
    :param app_id: the app id to load it on
    :type app_id: int
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

    :param config: The configuration to look things up in.
    :param section: The section name
    :type section: str
    :param item: The item name.
    :type item: str
    :rtype: str or None
    """
    value = config.get(section, item)
    if value == "None":
        return None
    return value


def read_config_int(config, section, item):
    """ Get the integer value of a config item, returning None if the value\
        is "None"

    :param config: The configuration to look things up in.
    :param section: The section name
    :type section: str
    :param item: The item name.
    :type item: str
    :rtype: int or None
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

    :param config: The configuration to look things up in.
    :param section: The section name
    :type section: str
    :param item: The item name.
    :type item: str
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

    :param folder: where to put this unique file
    :type folder: str
    :param filename: the name of the first part of the file without extension
    :type filename: str
    :param extension: extension of the file
    :type extension: str
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

    :param machine: the SpiNNaker machine
    :type machine: ~spinn_machine.Machine
    :param board_address: the board address to locate the chip of.
    :type board_address: str
    :return: The chip that supports that board address
    :rtype: ~spinn_machine.Chip
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
    :type executable_types: dict(ExecutableType,any)
    :param no_sync_changes: the number of times sync signals been sent
    :type no_sync_changes: int
    :return: dict of executable type to states.
    :rtype: tuple(dict(ExecutableType,~spinnman.model.enums.CPUState),\
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

    :param vertices: the vertices to convert to core subsets
    :param placements: the placements object
    :type placements: ~pacman.model.placements.Placements
    :return: the CoreSubSets of the vertices
    :rtype: ~spinn_machine.CoreSubsets
    """
    core_subsets = CoreSubsets()
    for vertex in vertices:
        placement = placements.get_placement_of_vertex(vertex)
        core_subsets.add_processor(placement.x, placement.y, placement.p)
    return core_subsets


def find_executable_start_type(machine_vertex, graph_mapper=None):
    if isinstance(machine_vertex, AbstractHasAssociatedBinary):
        return machine_vertex.get_binary_start_type()
    if graph_mapper is not None:
        app_vertex = graph_mapper.get_application_vertex(machine_vertex)
        if isinstance(app_vertex, AbstractHasAssociatedBinary):
            return app_vertex.get_binary_start_type()
    return None


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
        logger.warning(txrx.get_core_status_string(infos))
        logger.warning("Could not read information from cores {}".format(
            errors))


# TRICKY POINT: Have to delay the import to here because of import circularity
def _emergency_iobuf_extract(txrx, executable_targets):
    # pylint: disable=protected-access
    from spinn_front_end_common.interface.interface_functions import (
        ChipIOBufExtractor)
    sim = get_simulator()
    extractor = ChipIOBufExtractor(
        recovery_mode=True, filename_template="emergency_iobuf_{}_{}_{}.txt")
    extractor(txrx, executable_targets, sim._executable_finder,
              sim._app_provenance_file_path, sim._system_provenance_file_path,
              sim._mapping_outputs["BinaryToExecutableType"])


def emergency_recover_state_from_failure(txrx, app_id, vertex, placement):
    """ Used to get at least *some* information out of a core when something\
    goes badly wrong. Not a replacement for what abstract spinnaker base does.

    :param txrx: The transceiver.
    :type txrx: ~spinnman.transceiver.Transceiver
    :param app_id: The ID of the application.
    :type app_id: int
    :param vertex: The vertex to retrieve the IOBUF from if it is suspected\
        as being dead
    :type vertex: \
        ~spinn_front_end_common.abstract_models.AbstractHasAssociatedBinary
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
    :type txrx: ~spinnman.transceiver.Transceiver
    :param app_id: The ID of the application.
    :type app_id: int
    :param executable_targets: The what/where mapping
    :type executable_targets: ExecutableTargets
    """
    _emergency_state_check(txrx, app_id)
    _emergency_iobuf_extract(txrx, executable_targets)
