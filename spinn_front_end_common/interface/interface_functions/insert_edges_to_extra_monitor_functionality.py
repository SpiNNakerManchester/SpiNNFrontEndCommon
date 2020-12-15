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
    ExtraMonitorSupportMachineVertex)


class InsertEdgesToExtraMonitorFunctionality(object):
    """ Inserts edges between vertices who use MC speed up and its local\
        MC data gatherer.
    """

    __slots__ = [
        # Map of Chip(x,y) to the (Gather) vertex
        "_chip_to_gatherer_map",
        # Description of the machine on which job is being run
        "_machine",
        # Map of Core(x,y,p) to the Placement on that core
        "_placements"
    ]

    EDGE_LABEL = "edge between {} and {}"

    def __call__(self, machine_graph, placements, machine,
                 vertex_to_ethernet_connected_chip_mapping,
                 application_graph=None):
        """
        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
            the machine graph instance
        :param ~pacman.model.placements.Placements placements: the placements
        :param ~spinn_machine.Machine machine: the machine object
        :param vertex_to_ethernet_connected_chip_mapping:
            mapping between ethernet connected chips and packet gatherers
        :type vertex_to_ethernet_connected_chip_mapping:
            dict(tuple(int,int), DataSpeedUpPacketGatherMachineVertex)
        :param application_graph: the application graph
        :type application_graph:
            ~pacman.model.graphs.application.ApplicationGraph
        """
        # pylint: disable=too-many-arguments, attribute-defined-outside-init
        n_app_vertices = 0
        if application_graph is not None:
            n_app_vertices = application_graph.n_vertices
        self._chip_to_gatherer_map = vertex_to_ethernet_connected_chip_mapping
        self._machine = machine
        self._placements = placements

        progress = ProgressBar(
            machine_graph.n_vertices + n_app_vertices,
            "Inserting edges between vertices which require FR speed up "
            "functionality.")

        if application_graph is None:
            for vertex in progress.over(machine_graph.vertices):
                if isinstance(vertex, ExtraMonitorSupportMachineVertex):
                    self._process_mach_graph_vertex(vertex, machine_graph)
        else:
            for vertex in progress.over(machine_graph.vertices, False):
                if isinstance(vertex, ExtraMonitorSupportMachineVertex):
                    self._process_app_graph_vertex(
                        vertex, machine_graph, application_graph)

    def _process_app_graph_vertex(
            self, vertex, machine_graph, application_graph):
        """ Inserts edges as required for a given vertex

        :param ExtraMonitorSupportMachineVertex vertex: the extra monitor core
        :param ~.MachineGraph machine_graph: machine graph object
        :param ~.ApplicationGraph application_graph: app graph object; not None
        :rtype: None
        """
        gatherer = self._get_gatherer_vertex(vertex)

        # locate if edge is already built; if not, build it and do mapping
        if not self.__has_edge_already(vertex, gatherer, machine_graph):
            # See if there's an application edge already
            app_edge = self.__get_app_edge(
                application_graph, vertex.app_vertex, gatherer.app_vertex)
            if app_edge is None:
                app_edge = ApplicationEdge(
                    vertex.app_vertex, gatherer.app_vertex)
                application_graph.add_edge(
                    app_edge, PARTITION_ID_FOR_MULTICAST_DATA_SPEED_UP)
            # Use the application edge to build the machine edge
            edge = MachineEdge(
                vertex, gatherer, traffic_type=DataSpeedUp.TRAFFIC_TYPE,
                label=self.EDGE_LABEL.format(vertex, gatherer),
                app_edge=app_edge)
            machine_graph.add_edge(
                edge, PARTITION_ID_FOR_MULTICAST_DATA_SPEED_UP)

    def _process_mach_graph_vertex(self, vertex, machine_graph):
        """ Inserts edges as required for a given vertex

        :param ExtraMonitorSupportMachineVertex vertex: the extra monitor core
        :param ~.MachineGraph machine_graph:
            machine graph object, which is not associated with any application
            graph
        :rtype: None
        """
        gatherer = self._get_gatherer_vertex(vertex)

        # locate if edge is already built; if not, build it and do mapping
        if not self.__has_edge_already(vertex, gatherer, machine_graph):
            edge = MachineEdge(
                vertex, gatherer, traffic_type=DataSpeedUp.TRAFFIC_TYPE)
            machine_graph.add_edge(
                edge, PARTITION_ID_FOR_MULTICAST_DATA_SPEED_UP)

    def _get_gatherer_vertex(self, vertex):
        """
        :param ExtraMonitorSupportMachineVertex vertex:
        :rtype: DataSpeedUpPacketGatherMachineVertex
        """
        placement = self._placements.get_placement_of_vertex(vertex)
        chip = self._machine.get_chip_at(placement.x, placement.y)
        ethernet_chip = self._machine.get_chip_at(
            chip.nearest_ethernet_x, chip.nearest_ethernet_y)
        return self._chip_to_gatherer_map[ethernet_chip.x, ethernet_chip.y]

    @staticmethod
    def __get_app_edge(graph, source, destination):
        """
        :param ~.ApplicationGraph graph:
        :param ~.ApplicationVertex source:
        :param ~.ApplicationVertex destination:
        :rtype: ~.ApplicationEdge
        """
        for edge in graph.get_edges_ending_at_vertex(destination):
            if edge.pre_vertex == source:
                return edge
        return None

    @staticmethod
    def __has_edge_already(source, destination, graph):
        """ Checks if a edge already exists

        :param ~.AbstractVertex source: the source of the edge
        :param ~.AbstractVertex destination: destination of the edge
        :param ~.Graph graph: which graph to look in
        :return: Whether the edge was found
        :rtype: bool
        """
        return any(edge.pre_vertex == source
                   for edge in graph.get_edges_ending_at_vertex(destination))
