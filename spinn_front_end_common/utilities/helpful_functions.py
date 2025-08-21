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
from __future__ import annotations
import os
import logging
import struct
from typing import (
    Any, Collection, Dict, Iterable, List, Optional, Tuple, TYPE_CHECKING)
from spinn_utilities.log import FormatAdapter
from spinn_machine import CoreSubsets, Chip, Machine, MulticastRoutingEntry
from spinnman.model.enums import CPUState, ExecutableType
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.constants import (
    APP_PTR_TABLE_HEADER_BYTE_SIZE, APP_PTR_TABLE_REGION_BYTE_SIZE)
from spinn_front_end_common.utilities.exceptions import ConfigurationException
if TYPE_CHECKING:
    from pacman.model.placements import Placement
    from pacman.model.graphs.machine import MachineVertex
    from spinn_front_end_common.utility_models import (
        DataSpeedUpPacketGatherMachineVertex)

logger = FormatAdapter(logging.getLogger(__name__))
_n_word_structs: List[Optional[struct.Struct]] = []


def locate_extra_monitor_mc_receiver(
        placement_x: int, placement_y: int
        ) -> DataSpeedUpPacketGatherMachineVertex:
    """
    Get the data speed up gatherer that can be used to talk to a
    particular chip. This will be on the same board.

    :param placement_x: The X coordinate of the reference chip
    :param placement_y: The Y coordinate of the reference chip
    :return: Monitor on the Ethernet Chip of the board x, y is on
    """
    chip = FecDataView.get_chip_at(placement_x, placement_y)
    return FecDataView.get_gatherer_by_xy(
        chip.nearest_ethernet_x, chip.nearest_ethernet_y)


def read_data(x: int, y: int, address: int, length: int,
              data_format: str) -> int:
    """
    Reads and converts a single data item from memory.

    :param x: chip x
    :param y: chip y
    :param address: base address of the SDRAM chip to read
    :param length: length to read
    :param data_format:
        the format to read memory (see :py:func:`struct.pack`)
    :return: whatever is produced by unpacking the data
    """
    data = FecDataView.read_memory(x, y, address, length)
    return struct.unpack_from(data_format, data)[0]


def get_region_base_address_offset(
        app_data_base_address: int, region: int) -> int:
    """
    :param app_data_base_address: base address for the core
    :param region: the region ID we're looking for
    :returns: The address of the given region for the DSG.
    """
    return (app_data_base_address +
            APP_PTR_TABLE_HEADER_BYTE_SIZE +
            (region * APP_PTR_TABLE_REGION_BYTE_SIZE))


def locate_memory_region_for_placement(
        placement: Placement, region: int) -> int:
    """
    Get the address of a region for a placement.

    :param region: the region to locate the base address of
    :param placement:
        the placement object to get the region address of
    :return: the address
    """
    transceiver = FecDataView.get_transceiver()
    regions_base_address = transceiver.get_region_base_address(
        placement.x, placement.y, placement.p)

    # Get the position of the region in the pointer table
    element_addr = get_region_base_address_offset(regions_base_address, region)

    # Get the actual address of the region
    return transceiver.read_word(placement.x, placement.y, element_addr)


def convert_string_into_chip_and_core_subset(
        cores: Optional[str]) -> CoreSubsets:
    """
    Translate a string list of cores into a core subset.

    :param cores:
        string representing cores formatted as x,y,p[:x,y,p]*
    :returns: Core(s) read from the String
    """
    ignored_cores = CoreSubsets()
    if cores is not None and cores != "None":
        for downed_core in cores.split(":"):
            x, y, processor_id = downed_core.split(",")
            ignored_cores.add_processor(int(x), int(y), int(processor_id))
    return ignored_cores


def flood_fill_binary_to_spinnaker(binary: str) -> int:
    """
    Flood fills a binary to SpiNNaker.

    :param binary:
        The name of the file containing the APLX binary to load
    :return: the number of cores it was loaded onto
    """
    executable_targets = FecDataView.get_executable_targets()
    core_subset = executable_targets.get_cores_for_binary(binary)
    FecDataView.get_transceiver().execute_flood(
        core_subset, binary, FecDataView.get_app_id(), wait=True)
    return len(core_subset)


def generate_unique_folder_name(
        folder: str, filename: str, extension: str) -> str:
    """
    Generate a unique file name with a given extension in a given folder.

    :param folder: where to put this unique file
    :param filename:
        the name of the first part of the file without extension
    :param extension: extension of the file
    :return: file path with a unique addition
    """
    new_file_path = os.path.join(folder, f"{filename}{extension}")
    count = 2
    while os.path.exists(new_file_path):
        new_file_path = os.path.join(folder, f"{filename}_{count}{extension}")
        count += 1
    return new_file_path


def get_ethernet_chip(machine: Machine, board_address: str) -> Chip:
    """
    Locate the chip with the given board IP address.

    :param machine: the SpiNNaker machine
    :param board_address: the board address to locate the chip of.
    :return: The chip that supports that board address
    :raises ConfigurationException:
        when that board address has no chip associated with it
    """
    for chip in machine.ethernet_connected_chips:
        if chip.ip_address == board_address:
            return chip
    raise ConfigurationException(
        "cannot find the Ethernet connected chip with the "
        f"board address {board_address}")


def determine_flow_states(
        executable_types: Dict[ExecutableType, Any],
        no_sync_changes: int) -> Tuple[
            Dict[ExecutableType, Collection[CPUState]],
            Dict[ExecutableType, Collection[CPUState]]]:
    """
    Get the start and end states for these executable types.

    :param executable_types:
        the execute types to locate start and end states from
    :param  no_sync_changes: the number of times sync signals been sent
    :return: dict of executable type to states.
    """
    expected_start_states: Dict[ExecutableType, Collection[CPUState]] = dict()
    expected_end_states: Dict[ExecutableType, Collection[CPUState]] = dict()
    for start_type in executable_types.keys():
        # cores that ignore all control and are just running
        if start_type == ExecutableType.RUNNING:
            expected_start_states[ExecutableType.RUNNING] = (
                CPUState.RUNNING, CPUState.FINISHED)
            expected_end_states[ExecutableType.RUNNING] = (
                CPUState.RUNNING, CPUState.FINISHED)

        # cores that require a sync barrier
        elif start_type == ExecutableType.SYNC:
            expected_start_states[ExecutableType.SYNC] = (CPUState.SYNC0,)
            expected_end_states[ExecutableType.SYNC] = (CPUState.FINISHED,)

        # cores that use our simulation interface
        elif start_type == ExecutableType.USES_SIMULATION_INTERFACE:
            if no_sync_changes % 2 == 0:
                expected_start_states[start_type] = (CPUState.SYNC0,)
            else:
                expected_start_states[start_type] = (CPUState.SYNC1,)
            expected_end_states[start_type] = (CPUState.PAUSED,)

    # if no states, go boom.
    if not expected_start_states:
        raise ConfigurationException(
            f"Unknown executable start types {executable_types}")
    return expected_start_states, expected_end_states


def convert_vertices_to_core_subset(
        vertices: Iterable[MachineVertex]) -> CoreSubsets:
    """
    Converts vertices into core subsets.

    :param vertices:
        the vertices to convert to core subsets
    :return: the CoreSubSets of the vertices
    """
    core_subsets = CoreSubsets()
    for vertex in vertices:
        placement = FecDataView.get_placement_of_vertex(vertex)
        core_subsets.add_processor(placement.x, placement.y, placement.p)
    return core_subsets


def n_word_struct(n_words: int) -> struct.Struct:
    """
    Manages a precompiled cache of :py:class`~struct.Struct`\\s for
    parsing blocks of words.
    Thus, this::

        data = n_word_struct(n_words).unpack(data_blob)

    Is much like doing this::

        data = struct.unpack(f"<{n_words}I", data_blob)

    except quite a bit more efficient because things are shared including the
    cost of parsing the format.

    :param n_words: The number of *SpiNNaker words* to be handled.
    :return: A struct for working with that many words.
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


def get_defaultable_source_id(entry: MulticastRoutingEntry) -> int:
    """
    Hack to support the source requirement for the router compressor on chip.

    :param entry: the multicast router table entry.
    :return: return the source value
    """
    if entry.defaultable:
        return (list(entry.link_ids)[0] + 3) % 6
    elif entry.link_ids:
        return list(entry.link_ids)[0]
    return 0
