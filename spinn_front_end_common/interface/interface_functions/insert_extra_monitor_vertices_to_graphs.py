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


def insert_extra_monitor_vertices_to_graphs(placements):
    """
    Inserts the extra monitor vertices into the graph that correspond to
    the extra monitor cores required.

    :return: vertex to Ethernet connection map,
        list of extra_monitor_vertices,
        vertex_to_chip_map
    :rtype: tuple(
        dict(tuple(int,int),DataSpeedUpPacketGatherMachineVertex),
        list(ExtraMonitorSupportMachineVertex),
        dict(tuple(int,int),ExtraMonitorSupportMachineVertex))
    """
    # pylint: disable=too-many-arguments, attribute-defined-outside-init
    chip_to_gatherer_map = dict()
    vertex_to_chip_map = dict()
    machine = FecDataView.get_machine()
    ethernet_chips = list(machine.ethernet_connected_chips)
    progress = ProgressBar(
        len(ethernet_chips), "Inserting extra monitors into graphs")

    for eth in progress.over(machine.ethernet_connected_chips):
        gatherer = DataSpeedUpPacketGatherMachineVertex(
            x=eth.x, y=eth.y, ip_address=eth.ip_address)
        chip_to_gatherer_map[eth.x, eth.y] = gatherer
        cores = __cores(machine, eth.x, eth.y)
        p = cores[placements.n_placements_on_chip(eth.x, eth.y)]
        placements.add_placement(Placement(gatherer, eth.x, eth.y, p))
        for x, y in machine.get_existing_xys_by_ethernet(eth.x, eth.y):
            monitor = ExtraMonitorSupportMachineVertex()
            vertex_to_chip_map[x, y] = monitor
            cores = __cores(machine, x, y)
            p = cores[placements.n_placements_on_chip(x, y)]
            placements.add_placement(Placement(monitor, x, y, p))
    return chip_to_gatherer_map, vertex_to_chip_map


def __cores(machine, x, y):
    return [p.processor_id for p in machine.get_chip_at(x, y).processors
            if not p.is_monitor]
