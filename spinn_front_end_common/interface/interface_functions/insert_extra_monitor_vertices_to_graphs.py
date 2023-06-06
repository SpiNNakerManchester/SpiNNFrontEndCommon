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

from spinn_utilities.progress_bar import ProgressBar
from pacman.model.placements import Placement
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utility_models import (
    DataSpeedUpPacketGatherMachineVertex, ExtraMonitorSupportMachineVertex)
from spinn_front_end_common.utilities.utility_calls import (
    pick_core_for_system_placement)


def insert_extra_monitor_vertices_to_graphs(placements):
    """
    Inserts the extra monitor vertices into the graph that correspond to
    the extra monitor cores required.

    :param ~pacman.model.placements.Placements placements:
    :return: mapping from *Ethernet-enabled* chip locations to their gatherer,
        mapping from *all* chip locations to their extra monitor
    :rtype: tuple(
        dict(Chip,DataSpeedUpPacketGatherMachineVertex),
        dict(Chip,ExtraMonitorSupportMachineVertex))
    """
    chip_to_gatherer_map = dict()
    chip_to_monitor_map = dict()
    machine = FecDataView.get_machine()
    ethernet_chips = machine.ethernet_connected_chips
    progress = ProgressBar(
        len(ethernet_chips), "Inserting extra monitors into graphs")

    for eth in progress.over(ethernet_chips):
        gatherer = DataSpeedUpPacketGatherMachineVertex(
            x=eth.x, y=eth.y, ip_address=eth.ip_address)
        chip_to_gatherer_map[eth] = gatherer
        p = pick_core_for_system_placement(placements, eth.x, eth.y)
        placements.add_placement(Placement(gatherer, eth.x, eth.y, p))
        for x, y in machine.get_existing_xys_by_ethernet(eth.x, eth.y):
            monitor = ExtraMonitorSupportMachineVertex()
            chip_to_monitor_map[machine.get_chip_at(x, y)] = monitor
            p = pick_core_for_system_placement(placements, x, y)
            placements.add_placement(Placement(monitor, x, y, p))
    return chip_to_gatherer_map, chip_to_monitor_map
