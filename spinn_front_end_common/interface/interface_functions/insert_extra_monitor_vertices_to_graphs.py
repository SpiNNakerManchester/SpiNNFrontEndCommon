# Copyright (c) 2017 The University of Manchester
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
from typing import Tuple, Dict
from spinn_utilities.progress_bar import ProgressBar
from spinn_machine import Chip
from pacman.model.placements import Placement, Placements
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utility_models import (
    DataSpeedUpPacketGatherMachineVertex, ExtraMonitorSupportMachineVertex)
from spinn_front_end_common.utilities.utility_calls import (
    pick_core_for_system_placement)


def sample_speedup_vertex() -> DataSpeedUpPacketGatherMachineVertex:
    """
    Vertex to be added to every Ethernet chip Used for cost models

    :return: An unplaced Vertex
    """
    return DataSpeedUpPacketGatherMachineVertex(
        x=-1, y=-1, ip_address="sample")


def sample_monitor_vertex() -> ExtraMonitorSupportMachineVertex:
    """
    Vertex to be added to every Chip for cost models

    :return: An unplaced Vertex
    """
    return ExtraMonitorSupportMachineVertex()


def insert_extra_monitor_vertices_to_graphs(placements: Placements) -> Tuple[
        Dict[Chip, DataSpeedUpPacketGatherMachineVertex],
        Dict[Chip, ExtraMonitorSupportMachineVertex]]:
    """
    Inserts the extra monitor vertices into the graph that correspond to
    the extra monitor cores required.

    :param placements:
    :return: mapping from *Ethernet-enabled* chip locations to their gatherer,
        mapping from *all* chip locations to their extra monitor
    """
    chip_to_gatherer_map = dict()
    chip_to_monitor_map = dict()
    machine = FecDataView.get_machine()
    ethernet_chips = machine.ethernet_connected_chips
    progress = ProgressBar(
        len(ethernet_chips), "Inserting extra monitors into graphs")

    for eth in progress.over(ethernet_chips):
        assert eth.ip_address is not None
        gatherer = DataSpeedUpPacketGatherMachineVertex(
            x=eth.x, y=eth.y, ip_address=eth.ip_address)
        chip_to_gatherer_map[eth] = gatherer
        p = pick_core_for_system_placement(placements, eth)
        placements.add_placement(Placement(gatherer, eth.x, eth.y, p))
        for chip in machine.get_chips_by_ethernet(eth.x, eth.y):
            monitor = ExtraMonitorSupportMachineVertex()
            chip_to_monitor_map[chip] = monitor
            p = pick_core_for_system_placement(placements, chip)
            placements.add_placement(Placement(monitor, chip.x, chip.y, p))
    return chip_to_gatherer_map, chip_to_monitor_map
