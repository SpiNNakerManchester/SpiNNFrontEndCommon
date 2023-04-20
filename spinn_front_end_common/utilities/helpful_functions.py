# Copyright (c) 2014 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import logging
import struct
from spinn_utilities.log import FormatAdapter
from spinn_machine import CoreSubsets
from spinnman.model.enums import CPUState
from data_specification.constants import (
    APP_PTR_TABLE_HEADER_BYTE_SIZE, APP_PTR_TABLE_REGION_BYTE_SIZE)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.utility_objs import ExecutableType

logger = FormatAdapter(logging.getLogger(__name__))
_n_word_structs = []


def locate_extra_monitor_mc_receiver(placement_x, placement_y):
    """
    Get the data speed up gatherer that can be used to talk to a
    particular chip. This will be on the same board.

    :param int placement_x: The X coordinate of the reference chip
    :param int placement_y: The Y coordinate of the reference chip
    :rtype: DataSpeedUpPacketGatherMachineVertex
    """
    chip = FecDataView.get_chip_at(placement_x, placement_y)
    return FecDataView.get_gatherer_by_xy(
        chip.nearest_ethernet_x, chip.nearest_ethernet_y)


def read_data(x, y, address, length, data_format):
    """
    Reads and converts a single data item from memory.

    :param int x: chip x
    :param int y: chip y
    :param int address: base address of the SDRAM chip to read
    :param int length: length to read
    :param str data_format:
        the format to read memory (see :py:func:`struct.pack`)
    :return: whatever is produced by unpacking the data
    :rtype: tuple
    """
    # pylint: disable=too-many-arguments
    data = FecDataView.read_memory(x, y, address, length)
    return struct.unpack_from(data_format, data)[0]


def write_address_to_user0(x, y, p, address):
    """
    Writes the given address into the user_0 register of the given core.

    :param int x: Chip coordinate.
    :param int y: Chip coordinate.
    :param int p: Core ID on chip.
    :param int address: Value to write (32-bit integer)
    """
    txrx = FecDataView.get_transceiver()
    user_0_address = txrx.get_user_0_register_address_from_core(p)
    txrx.write_memory(x, y, user_0_address, address)


def write_address_to_user1(x, y, p, address):
    """
    Writes the given address into the user_1 register of the given core.

    :param int x: Chip coordinate.
    :param int y: Chip coordinate.
    :param int p: Core ID on chip.
    :param int address: Value to write (32-bit integer)
    """
    txrx = FecDataView.get_transceiver()
    user_1_address = txrx.get_user_1_register_address_from_core(p)
    txrx.write_memory(x, y, user_1_address, address)


def get_region_base_address_offset(app_data_base_address, region):
    """
    Find the address of the of a given region for the DSG.

    :param int app_data_base_address: base address for the core
    :param int region: the region ID we're looking for
    """
    return (app_data_base_address +
            APP_PTR_TABLE_HEADER_BYTE_SIZE +
            (region * APP_PTR_TABLE_REGION_BYTE_SIZE))


def locate_memory_region_for_placement(placement, region):
    """
    Get the address of a region for a placement.

    :param int region: the region to locate the base address of
    :param ~pacman.model.placements.Placement placement:
        the placement object to get the region address of
    :param ~spinnman.transceiver.Transceiver transceiver:
        the python interface to the SpiNNaker machine
    :return: the address
    :rtype: int
    """
    transceiver = FecDataView.get_transceiver()
    regions_base_address = transceiver.get_cpu_information_from_core(
        placement.x, placement.y, placement.p).user[0]

    # Get the position of the region in the pointer table
    element_addr = get_region_base_address_offset(regions_base_address, region)

    # Get the actual address of the region
    return transceiver.read_word(placement.x, placement.y, element_addr)


def convert_string_into_chip_and_core_subset(cores):
    """
    Translate a string list of cores into a core subset.

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


def flood_fill_binary_to_spinnaker(binary):
    """
    Flood fills a binary to SpiNNaker.

    :param str binary:
        The name of the file containing the APLX binary to load
    :return: the number of cores it was loaded onto
    :rtype: int
    """
    executable_targets = FecDataView.get_executable_targets()
    core_subset = executable_targets.get_cores_for_binary(binary)
    FecDataView.get_transceiver().execute_flood(
        core_subset, binary, FecDataView.get_app_id(), wait=True,
        is_filename=True)
    return len(core_subset)


def generate_unique_folder_name(folder, filename, extension):
    """
    Generate a unique file name with a given extension in a given folder.

    :param str folder: where to put this unique file
    :param str filename:
        the name of the first part of the file without extension
    :param str extension: extension of the file
    :return: file path with a unique addition
    :rtype: str
    """
    new_file_path = os.path.join(folder, f"{filename}{extension}")
    count = 2
    while os.path.exists(new_file_path):
        new_file_path = os.path.join(folder, f"{filename}_{count}{extension}")
        count += 1
    return new_file_path


def get_ethernet_chip(machine, board_address):
    """
    Locate the chip with the given board IP address.

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
        "cannot find the Ethernet connected chip with the "
        f"board address {board_address}")


def determine_flow_states(executable_types, no_sync_changes):
    """
    Get the start and end states for these executable types.

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
            f"Unknown executable start types {executable_types}")
    return expected_start_states, expected_end_states


def convert_vertices_to_core_subset(vertices):
    """
    Converts vertices into core subsets.

    :param iterable(~pacman.model.graphs.machine.MachineVertex) vertices:
        the vertices to convert to core subsets
    :return: the CoreSubSets of the vertices
    :rtype: ~spinn_machine.CoreSubsets
    """
    core_subsets = CoreSubsets()
    for vertex in vertices:
        placement = FecDataView.get_placement_of_vertex(vertex)
        core_subsets.add_processor(placement.x, placement.y, placement.p)
    return core_subsets


def n_word_struct(n_words):
    """
    Manages a precompiled cache of :py:class`~struct.Struct`\\s for
    parsing blocks of words.
    Thus, this::

        data = n_word_struct(n_words).unpack(data_blob)

    Is much like doing this::

        data = struct.unpack(f"<{n_words}I", data_blob)

    except quite a bit more efficient because things are shared including the
    cost of parsing the format.

    :param int n_words: The number of *SpiNNaker words* to be handled.
    :return: A struct for working with that many words.
    :rtype: ~struct.Struct
    """
    # pylint: disable=global-statement
    global _n_word_structs
    while len(_n_word_structs) < n_words + 1:
        _n_word_structs += [None] * (n_words + 1 - len(_n_word_structs))
    s = _n_word_structs[n_words]
    if s is not None:
        return s
    new_struct = struct.Struct(f"<{n_words}I")
    _n_word_structs[n_words] = new_struct
    return new_struct


def get_defaultable_source_id(entry):
    """
    Hack to support the source requirement for the router compressor on chip.

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
