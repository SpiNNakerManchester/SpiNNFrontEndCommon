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

from spinn_front_end_common.utility_models import LivePacketGatherMachineVertex
from pacman.model.placements import Placement


def insert_live_packet_gatherers_to_graphs(
        live_packet_gatherer_parameters, machine, placements):
    """ Add LPG vertices on Ethernet connected chips as required.

    :param live_packet_gatherer_parameters:
        the Live Packet Gatherer parameters requested by the script
    :type live_packet_gatherer_parameters:
        dict(LivePacketGatherParameters,
        list(tuple(~pacman.model.graphs.AbstractVertex, list(str))))
    :param ~spinn_machine.Machine machine:
        the SpiNNaker machine as discovered
    :param Placements placements:
        exiting placements to be added to
    :return: mapping of (LPG parameters, Ethernet coordinates) to
        LPG machine vertex
    :rtype: dict((LivePacketGatherParameters,int,int),LivePacketGather)
    """
    # Keep track of the vertices added by parameters and Ethernet chip
    lpg_params_to_vertices = dict()

    # for every Ethernet connected chip, add the gatherers required
    for params in live_packet_gatherer_parameters:
        for eth in machine.ethernet_connected_chips:
            lpg_vtx = LivePacketGatherMachineVertex(params)
            cores = __cores(machine, eth.x, eth.y)
            p = cores[placements.n_placements_on_chip(eth.x, eth.y) + 1]
            placements.add_placement(Placement(lpg_vtx, eth.x, eth.y, p))
            lpg_params_to_vertices[params, eth.x, eth.y] = lpg_vtx

    return lpg_params_to_vertices


def __cores(machine, x, y):
    return [p.processor_id for p in machine.get_chip_at(x, y).processors
            if not p.is_monitor]
