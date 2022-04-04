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

from spinn_utilities.progress_bar import ProgressBar
from pacman.model.placements import Placement
from spinn_front_end_common.utility_models import (
    DataSpeedUpPacketGatherMachineVertex, ExtraMonitorSupportMachineVertex)


def insert_extra_monitor_vertices_to_graphs(
        machine, application_graph, placements):
    """ Inserts the extra monitor vertices into the graph that correspond to\
        the extra monitor cores required.

    :param ~spinn_machine.Machine machine: spinnMachine instance
    :param int n_cores_to_allocate:
        number of cores to allocate for reception
    :param application_graph: app graph
    :type application_graph:
        ~pacman.model.graphs.application.ApplicationGraph
    :param Placements placements: Where to put placements
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
