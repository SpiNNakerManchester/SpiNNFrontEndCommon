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

from spinn_front_end_common.utility_models import LivePacketGather
from spinn_front_end_common.interface.splitter_selectors import (
    LivePacketGatherSplitter)


class InsertLivePacketGatherersToGraphs(object):
    """ Adds LPGs as required into a given graph.
    """

    __slots__ = []

    def __call__(
            self, live_packet_gatherer_parameters, machine, application_graph):
        """ Add LPG vertices on Ethernet connected chips as required.

        :param live_packet_gatherer_parameters:
            the Live Packet Gatherer parameters requested by the script
        :type live_packet_gatherer_parameters:
            dict(LivePacketGatherParameters,
            list(tuple(~pacman.model.graphs.AbstractVertex, list(str))))
        :param ~spinn_machine.Machine machine:
            the SpiNNaker machine as discovered
        :param application_graph: the application graph
        :type application_graph:
            ~pacman.model.graphs.application.ApplicationGraph
        :return: mapping between LPG parameters and LPG application and
            machine vertices
        :rtype: dict(LivePacketGatherParameters,LivePacketGather)
        """

        # Keep track of the vertices added by parameters and board address
        lpg_params_to_vertices = dict()

        # for every Ethernet connected chip, add the gatherers required
        for params in live_packet_gatherer_parameters:
            lpg_app_vtx = LivePacketGather(params)
            lpg_app_vtx.splitter = LivePacketGatherSplitter()
            lpg_app_vtx.splitter.really_create_machine_vertices(machine)
            application_graph.add_vertex(lpg_app_vtx)
            lpg_params_to_vertices[params] = lpg_app_vtx

        return lpg_params_to_vertices
