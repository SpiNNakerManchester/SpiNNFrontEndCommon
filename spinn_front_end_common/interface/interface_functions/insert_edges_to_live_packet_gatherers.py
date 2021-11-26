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
from pacman.model.graphs.application import ApplicationEdge


class InsertEdgesToLivePacketGatherers(object):
    """ Add edges from the recorded vertices to the local Live PacketGatherers.
    """

    __slots__ = [
        # the mapping of LPG parameters to machine vertices
        "_lpg_to_vertex",
        # the SpiNNaker machine
        "_machine",
        # the placements object
        "_placements"
    ]

    def __call__(
            self, live_packet_gatherer_parameters, placements,
            live_packet_gatherers_to_vertex_mapping, machine,
            app_graph):
        """
        :param live_packet_gatherer_parameters: the set of parameters
        :type live_packet_gatherer_parameters:
            dict(LivePacketGatherParameters,
            list(tuple(~pacman.model.graphs.AbstractVertex, list(str))))
        :param ~pacman.model.placements.Placements placements:
            the placements object
        :param live_packet_gatherers_to_vertex_mapping:
            the mapping of LPG parameters and the machine vertices associated
            with it
        :type live_packet_gatherers_to_vertex_mapping:
            dict(LivePacketGatherParameters, LivePacketGather)
        :param ~spinn_machine.Machine machine: the SpiNNaker machine
        :param application_graph: the application graph
        :type application_graph:
            ~pacman.model.graphs.application.ApplicationGraph
        """
        # pylint: disable=too-many-arguments, attribute-defined-outside-init

        # These are all contextual, and unmodified by this algorithm
        self._lpg_to_vertex = live_packet_gatherers_to_vertex_mapping
        self._machine = machine
        self._placements = placements

        progress = ProgressBar(
            live_packet_gatherer_parameters,
            string_describing_what_being_progressed=(
                "Adding edges to the machine graph between the vertices to "
                "which live output has been requested and its local Live "
                "Packet Gatherer"))

        for lpg_params in progress.over(live_packet_gatherer_parameters):
            # locate vertices to connect to a LPG with these params
            for app_vertex, part_ids in live_packet_gatherer_parameters[
                    lpg_params]:

                lpg_app_vertex = self._lpg_to_vertex[lpg_params]
                for part_id in part_ids:
                    app_edge = ApplicationEdge(app_vertex, lpg_app_vertex)
                    app_graph.add_edge(app_edge, part_id)
                    part = app_graph\
                        .get_outgoing_edge_partition_starting_at_vertex(
                            app_vertex, part_id)

                    m_vertices = app_vertex.splitter.get_out_going_vertices(
                        part)
                    for m_vertex in m_vertices:
                        lpg_app_vertex.splitter.associate(
                            machine, m_vertex, placements)
