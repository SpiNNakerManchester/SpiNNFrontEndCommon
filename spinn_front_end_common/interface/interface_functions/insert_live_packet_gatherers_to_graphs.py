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
from spinn_front_end_common.utility_models import (
    LivePacketGather, LivePacketGatherMachineVertex)


class InsertLivePacketGatherersToGraphs(object):
    """ Adds LPGs as required into a given graph.
    """

    __slots__ = [
        "_machine_graph",
        "_application_graph"]

    def __call__(
            self, live_packet_gatherer_parameters, machine, machine_graph,
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
        :return: mapping between LPG parameters and LPG vertex
        :rtype: dict(LivePacketGatherParameters,
            dict(tuple(int,int),LivePacketGatherMachineVertex))
        """

        self._machine_graph = machine_graph
        self._application_graph = application_graph

        # create progress bar
        progress = ProgressBar(
            machine.ethernet_connected_chips,
            string_describing_what_being_progressed=(
                "Adding Live Packet Gatherers to Graph"))

        # Keep track of the vertices added by parameters and board address
        lpg_params_to_vertices = defaultdict(dict)

        # for every Ethernet connected chip, add the gatherers required
        if application_graph is not None:
            for chip in progress.over(machine.ethernet_connected_chips):
                for params in live_packet_gatherer_parameters:
                    if (params.board_address is None or
                            params.board_address == chip.ip_address):
                        lpg_params_to_vertices[params][chip.x, chip.y] = \
                            self._add_app_lpg_vertex(chip, params)
        else:
            for chip in progress.over(machine.ethernet_connected_chips):
                for params in live_packet_gatherer_parameters:
                    if (params.board_address is None or
                            params.board_address == chip.ip_address):
                        lpg_params_to_vertices[params][chip.x, chip.y] = \
                            self._add_mach_lpg_vertex(chip, params)

        return lpg_params_to_vertices

    def _add_app_lpg_vertex(self, chip, params):
        """ Adds a LPG vertex to a machine graph that has an associated\
            application graph.

        :param ~.Chip chip:
        :param LivePacketGatherParameters params:
        :rtype: LivePacketGatherMachineVertex
        """
        app_vtx = LivePacketGather(params)
        self._application_graph.add_vertex(app_vtx)
        # No need to handle resources when allocating; LPG has core to itself
        vtx = app_vtx.create_machine_vertex(
            vertex_slice=None, resources_required=None,
            label="LivePacketGatherer",
            constraints=[ChipAndCoreConstraint(x=chip.x, y=chip.y)])
        self._machine_graph.add_vertex(vtx)
        return vtx

    def _add_mach_lpg_vertex(self, chip, params):
        """ Adds a LPG vertex to a machine graph without an associated\
            application graph.

        :param ~.Chip chip:
        :param LivePacketGatherParameters params:
        :rtype: LivePacketGatherMachineVertex
        """
        vtx = LivePacketGatherMachineVertex(
            params, constraints=[ChipAndCoreConstraint(x=chip.x, y=chip.y)])
        self._machine_graph.add_vertex(vtx)
        return vtx
