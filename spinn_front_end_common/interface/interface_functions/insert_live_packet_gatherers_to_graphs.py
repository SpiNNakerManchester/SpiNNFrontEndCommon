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
from pacman.model.graphs.common import Slice
from pacman.model.constraints.placer_constraints import ChipAndCoreConstraint
from spinn_front_end_common.utility_models import (
    LivePacketGather, LivePacketGatherMachineVertex)


class InsertLivePacketGatherersToGraphs(object):
    """ Adds LPGs as required into a given graph.

    :param live_packet_gatherer_parameters:
        the Live Packet Gatherer parameters requested by the script
    :type live_packet_gatherer_parameters:
        dict(LivePacketGatherParameters,
        list(tuple(~pacman.model.graphs.AbstractVertex, list(str))))
    :param ~spinn_machine.Machine machine: the SpiNNaker machine as discovered
    :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
        the machine graph
    :param ~pacman.model.graphs.application.ApplicationGraph application_graph:
        the application graph
    :return: mapping between LPG parameters and LPG vertex
    :rtype: dict(LivePacketGatherParameters,
        dict(tuple(int,int),LivePacketGatherMachineVertex))

    """

    def __call__(
            self, live_packet_gatherer_parameters, machine, machine_graph,
            timestep_in_us, application_graph=None, graph_mapper=None):
        """ Add LPG vertices on Ethernet connected chips as required.

        :param live_packet_gatherer_parameters:\
            the Live Packet Gatherer parameters requested by the script
        :type live_packet_gatherer_parameters:
            dict(LivePacketGatherParameters,
            list(tuple(~.AbstractVertex, list(str))))
        :param ~.Machine machine: the SpiNNaker machine as discovered
        :param ~.MachineGraph machine_graph:
        :param int timestep_in_us: the timestep in us to apply to the vertexes
        :param ~.ApplicationGraph application_graph: the application graph
        :param machine_graph: the machine graph
        :return: mapping between LPG parameters and LPG vertex
        :rtype: dict(LivePacketGatherParameters,
            dict(tuple(int,int),LivePacketGatherMachineVertex))
        """
        # pylint: disable=too-many-arguments

        # create progress bar
        progress = ProgressBar(
            machine.ethernet_connected_chips,
            string_describing_what_being_progressed=(
                "Adding Live Packet Gatherers to Graph"))

        # Keep track of the vertices added by parameters and board address
        lpg_params_to_vertices = defaultdict(dict)

        if timestep_in_us is None:
            raise NotImplementedError("Unable to run with a None Timestep.")

        # for every Ethernet connected chip, add the gatherers required
        for chip in progress.over(machine.ethernet_connected_chips):
            for params in live_packet_gatherer_parameters:
                if (params.board_address is None or
                        params.board_address == chip.ip_address):
                    lpg_params_to_vertices[params][chip.x, chip.y] = \
                        self._add_lpg_vertex(
                            application_graph, graph_mapper, machine_graph,
                            chip, params, timestep_in_us)

        return lpg_params_to_vertices

    def _add_lpg_vertex(
            self, app_graph, mapper, m_graph, chip, params, timestep_in_us):
        # pylint: disable=too-many-arguments
        if app_graph is not None:
            _slice = Slice(0, 0)
            app_vtx = LivePacketGather(params, timestep_in_us=timestep_in_us)
            app_graph.add_vertex(app_vtx)
            resources = app_vtx.get_resources_used_by_atoms(_slice)
            m_vtx = app_vtx.create_machine_vertex(
                _slice, resources, label=params.label)
            mapper.add_vertex_mapping(m_vtx, _slice, app_vtx)
        else:
            m_vtx = LivePacketGatherMachineVertex(timestep_in_us, params)

        m_vtx.add_constraint(ChipAndCoreConstraint(x=chip.x, y=chip.y))
        m_graph.add_vertex(m_vtx)
        return m_vtx
