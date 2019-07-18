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
from pacman.model.graphs.machine import MachineEdge
from spinn_front_end_common.utilities.constants import (
    PARTITION_ID_FOR_MULTICAST_DATA_SPEED_UP)
from spinn_front_end_common.utility_models import (
    DataSpeedUpPacketGatherMachineVertex as DataSpeedUp,
    ExtraMonitorSupport, ExtraMonitorSupportMachineVertex)


class InsertEdgesToExtraMonitorFunctionality(object):
    """ Inserts edges between vertices who use MC speed up and its local\
        MC data gatherer.
    """

    def __call__(self, machine_graph, placements, machine,
                 vertex_to_ethernet_connected_chip_mapping,
                 application_graph=None, graph_mapper=None):
        """
        :param machine_graph: the machine graph instance
        :param placements: the placements
        :param machine: the machine object
        :param application_graph: the application graph
        :param vertex_to_ethernet_connected_chip_mapping: \
            mapping between ethernet connected chips and packet gatherers
        :param graph_mapper: the graph mapper
        :rtype: None
        """
        # pylint: disable=too-many-arguments
        n_app_vertices = 0
        if application_graph is not None:
            n_app_vertices = application_graph.n_vertices

        progress = ProgressBar(
            machine_graph.n_vertices + n_app_vertices,
            "Inserting edges between vertices which require FR speed up "
            "functionality.")

        for vertex in progress.over(machine_graph.vertices, False):
            if isinstance(vertex, ExtraMonitorSupportMachineVertex):
                self._process_vertex(
                    vertex, machine, placements, machine_graph,
                    vertex_to_ethernet_connected_chip_mapping,
                    application_graph, graph_mapper)

        if application_graph is not None:
            for vertex in progress.over(application_graph.vertices, False):
                if isinstance(vertex, ExtraMonitorSupport):
                    machine_verts = graph_mapper.get_machine_vertices(vertex)
                    for machine_vertex in machine_verts:
                        self._process_vertex(
                            machine_vertex, machine, placements, machine_graph,
                            vertex_to_ethernet_connected_chip_mapping,
                            application_graph, graph_mapper)
        progress.end()

    def _process_vertex(
            self, vertex, machine, placements, machine_graph,
            vertex_to_ethernet_connected_chip_mapping, application_graph,
            graph_mapper):
        """ Inserts edges as required for a given vertex

        :param vertex: the extra monitor core
        :param machine: the spinnMachine instance
        :param placements: the placements object
        :param machine_graph: machine graph object
        :param vertex_to_ethernet_connected_chip_mapping: \
            the ethernet to multicast gatherer map
        :param application_graph: app graph object
        :param graph_mapper: the mapping between app and machine graph
        :rtype: None
        """
        # pylint: disable=too-many-arguments
        data_gatherer_vertex = self._get_gatherer_vertex(
            machine, vertex_to_ethernet_connected_chip_mapping, placements,
            vertex)

        # locate if edge is already built; if not, build it and do mapping
        if not self._has_edge_already(
                vertex, data_gatherer_vertex, machine_graph):
            machine_edge = MachineEdge(
                vertex, data_gatherer_vertex,
                traffic_type=DataSpeedUp.TRAFFIC_TYPE)
            machine_graph.add_edge(
                machine_edge, PARTITION_ID_FOR_MULTICAST_DATA_SPEED_UP)

            if application_graph is not None:
                app_source = graph_mapper.get_application_vertex(vertex)
                app_dest = graph_mapper.get_application_vertex(
                    data_gatherer_vertex)

                # locate if edge is already built; if not, build it and map it
                if not self._has_edge_already(
                        app_source, app_dest, application_graph):
                    app_edge = ApplicationEdge(
                        app_source, app_dest,
                        traffic_type=DataSpeedUp.TRAFFIC_TYPE)
                    application_graph.add_edge(
                        app_edge, PARTITION_ID_FOR_MULTICAST_DATA_SPEED_UP)
                    graph_mapper.add_edge_mapping(machine_edge, app_edge)

    @staticmethod
    def _get_gatherer_vertex(machine, v_to_2_chip_map, placements, vertex):
        placement = placements.get_placement_of_vertex(vertex)
        chip = machine.get_chip_at(placement.x, placement.y)
        ethernet_chip = machine.get_chip_at(
            chip.nearest_ethernet_x, chip.nearest_ethernet_y)
        return v_to_2_chip_map[ethernet_chip.x, ethernet_chip.y]

    @staticmethod
    def _has_edge_already(source, destination, graph):
        """ Checks if a edge already exists

        :param source: the source of the edge
        :param destination: destination of the edge
        :param graph: which graph to look in
        :return: Whether the edge was found
        :rtype: bool
        """
        return any(edge.pre_vertex == source
                   for edge in graph.get_edges_ending_at_vertex(destination))
