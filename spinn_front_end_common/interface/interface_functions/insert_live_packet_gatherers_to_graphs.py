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

from collections import defaultdict
from spinn_utilities.progress_bar import ProgressBar
from pacman.model.constraints.placer_constraints import ChipAndCoreConstraint
from spinn_front_end_common.utility_models import LivePacketGather


def insert_live_packet_gatherers_to_graphs(
        live_packet_gatherer_parameters, machine, machine_graph,
        application_graph=None):
    """ Add LPG vertices on Ethernet connected chips as required.

    :param live_packet_gatherer_parameters:
        the Live Packet Gatherer parameters requested by the script
    :type live_packet_gatherer_parameters:
        dict(LivePacketGatherParameters,
        list(tuple(~pacman.model.graphs.AbstractVertex, list(str))))
    :param ~spinn_machine.Machine machine:
        the SpiNNaker machine as discovered
    :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
        the machine graph
    :param application_graph: the application graph
    :type application_graph:
        ~pacman.model.graphs.application.ApplicationGraph
    :return: mapping between LPG parameters and LPG application and
        machine vertices
    :rtype: dict(LivePacketGatherParameters,
        tuple(LivePacketGather or None,
        dict(tuple(int,int),LivePacketGatherMachineVertex)))
    """
    inserter = _InsertLivePacketGatherersToGraphs(
        machine_graph, application_graph)
    return inserter._run(live_packet_gatherer_parameters, machine)


class _InsertLivePacketGatherersToGraphs(object):
    """ Adds LPGs as required into a given graph.
    """

    __slots__ = [
        "_machine_graph",
        "_application_graph"]

    def __init__(self,  machine_graph, application_graph):
        """
        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
            the machine graph
        :param application_graph: the application graph
        :type application_graph:
            ~pacman.model.graphs.application.ApplicationGraph
        """
        self._machine_graph = machine_graph
        self._application_graph = application_graph

    def _run(self, live_packet_gatherer_parameters, machine,):
        """ Add LPG vertices on Ethernet connected chips as required.

        :param live_packet_gatherer_parameters:
            the Live Packet Gatherer parameters requested by the script
        :type live_packet_gatherer_parameters:
            dict(LivePacketGatherParameters,
            list(tuple(~pacman.model.graphs.AbstractVertex, list(str))))
        :param ~spinn_machine.Machine machine:
            the SpiNNaker machine as discovered
        :return: mapping between LPG parameters and LPG application and
            machine vertices
        :rtype: dict(LivePacketGatherParameters,
            tuple(LivePacketGather or None,
            dict(tuple(int,int),LivePacketGatherMachineVertex)))
        """
        # create progress bar
        progress = ProgressBar(
            machine.ethernet_connected_chips,
            string_describing_what_being_progressed=(
                "Adding Live Packet Gatherers to Graph"))

        # Keep track of the vertices added by parameters and board address
        lpg_params_to_vertices = defaultdict(dict)

        # for every Ethernet connected chip, add the gatherers required
        for params in live_packet_gatherer_parameters:
            lpg_app_vtx = LivePacketGather(params)
            self._application_graph.add_vertex(lpg_app_vtx)
            mac_vtxs = dict()
            for chip in progress.over(machine.ethernet_connected_chips):
                mac_vtxs[chip.x, chip.y] = self._add_app_lpg_vertex(
                    lpg_app_vtx, chip)
            lpg_params_to_vertices[params] = (lpg_app_vtx, mac_vtxs)

        return lpg_params_to_vertices

    def _add_app_lpg_vertex(self, lpg_app_vtx, chip):
        """ Adds a LPG vertex to a machine graph that has an associated\
            application graph.

        :param ~.Chip chip:
        :param LivePacketGather lpg_app_vtx:
        :rtype: LivePacketGatherMachineVertex
        """

        # No need to handle resources when allocating; LPG has core to itself
        vtx = lpg_app_vtx.create_machine_vertex(
            vertex_slice=None, resources_required=None,
            label="LivePacketGatherer",
            constraints=[ChipAndCoreConstraint(x=chip.x, y=chip.y)])
        self._machine_graph.add_vertex(vtx)
        return vtx
