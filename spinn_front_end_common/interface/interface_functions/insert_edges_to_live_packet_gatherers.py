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
from spinn_front_end_common.utilities.exceptions import ConfigurationException


class InsertEdgesToLivePacketGatherers(object):
    """ Add edges from the recorded vertices to the local Live PacketGatherers.
    """

    def __call__(
            self, live_packet_gatherer_parameters, placements,
            live_packet_gatherers_to_vertex_mapping, machine,
            machine_graph, application_graph=None, graph_mapper=None):
        """
        :param live_packet_gatherer_parameters: the set of parameters
        :param placements: the placements object
        :param live_packet_gatherers_to_vertex_mapping:\
            the mapping of LPG parameters and the machine vertices associated\
            with it
        :param machine: the SpiNNaker machine
        :param machine_graph: the machine graph
        :param application_graph: the application graph
        :param graph_mapper: \
            the mapping between application and machine graphs
        :rtype: None
        """
        # pylint: disable=too-many-arguments
        progress = ProgressBar(
            live_packet_gatherer_parameters,
            string_describing_what_being_progressed=(
                "Adding edges to the machine graph between the vertices to "
                "which live output has been requested and its local Live "
                "Packet Gatherer"))

        for lpg_params in progress.over(live_packet_gatherer_parameters):
            # locate vertices needed to be connected to a LPG with these params
            for vertex, p_ids in live_packet_gatherer_parameters[lpg_params]:
                self._connect_lpg_vertex(
                    application_graph, graph_mapper, machine,
                    placements, machine_graph, vertex,
                    live_packet_gatherers_to_vertex_mapping, lpg_params, p_ids)

    def _connect_lpg_vertex(
            self, app_graph, mapper, machine, placements, m_graph, vertex,
            lpg_to_vertex, lpg_params, partition_ids):
        # pylint: disable=too-many-arguments

        # Find all Live Gatherer machine vertices
        m_lpgs = lpg_to_vertex[lpg_params]

        # If it is an application graph, find the machine vertices
        if app_graph is not None:
            # flag for ensuring we don't add the edge to the app
            # graph many times
            app_graph_edges = None

            # iterate through the associated machine vertices
            machine_vertices = mapper.get_machine_vertices(vertex)
            for machine_vertex in machine_vertices:
                # add a edge between the closest LPG and the vertex
                machine_edges, machine_lpg = self._process_m_vertex(
                    machine_vertex, m_lpgs, machine, placements,
                    m_graph, partition_ids)

                # update the app graph and graph mapper
                app_graph_edges = self._update_app_graph_and_mapper(
                    app_graph, mapper, machine_lpg, vertex,
                    partition_ids, machine_edges, app_graph_edges)
        else:
            # add a edge between the closest LPG and the vertex
            self._process_m_vertex(
                vertex, m_lpgs, machine, placements,
                m_graph, partition_ids)

    def _process_m_vertex(
            self, machine_vertex, m_lpgs, machine,
            placements, machine_graph, partition_ids):
        """ Locates and places an edge for a machine vertex.

        :param machine_vertex: the machine vertex that needs an edge to a LPG
        :param m_lpgs:\
            dict of chip placed on to gatherers that are associated with the\
            parameters
        :param machine: the SpiNNaker machine object
        :param placements: the placements object
        :param machine_graph: the machine graph object
        :param partition_id: the partition ID to add to the edge
        :return: machine edge and the LPG vertex
        """
        # pylint: disable=too-many-arguments

        # locate the LPG that's closest to this vertex
        machine_lpg = self._find_closest_live_packet_gatherer(
            machine_vertex, m_lpgs, machine, placements)

        # add edge for the machine graph
        machine_edges = dict()
        for partition_id in partition_ids:
            machine_edge = MachineEdge(machine_vertex, machine_lpg)
            machine_graph.add_edge(machine_edge, partition_id)
            machine_edges[partition_id] = machine_edge

        # return the machine edge
        return machine_edges, machine_lpg

    @staticmethod
    def _update_app_graph_and_mapper(
            application_graph, graph_mapper, machine_lpg, vertex,
            partition_ids, machine_edges, app_graph_edges):
        """ Handles changes to the application graph and graph mapper.

        :param application_graph: the application graph
        :param graph_mapper: the graph mapper
        :param machine_lpg: the machine LPG
        :param vertex: the application vertex to link to
        :param partition_id: the partition ID to put the edge on
        :return: the application edge for this vertex and LPG
        :rtype: ~pacman.model.graph.application.ApplicationEdge
        """
        # pylint: disable=too-many-arguments

        # locate app vertex for LPG
        lpg_app_vertex = graph_mapper.get_application_vertex(machine_lpg)

        # if not built the app edge, add the app edge now
        if app_graph_edges is None:
            app_graph_edges = dict()
            for partition_id in partition_ids:
                app_graph_edge = ApplicationEdge(vertex, lpg_app_vertex)
                application_graph.add_edge(app_graph_edge, partition_id)
                app_graph_edges[partition_id] = app_graph_edge

        # add mapping between the app edge and the machine edge
        for partition_id in partition_ids:
            graph_mapper.add_edge_mapping(
                machine_edges[partition_id], app_graph_edges[partition_id])

        # return the app edge for reuse as needed
        return app_graph_edges

    @staticmethod
    def _find_closest_live_packet_gatherer(
            machine_vertex, machine_lpgs, machine, placements):
        """ Locates the LPG on the nearest Ethernet-connected chip to the\
            machine vertex in question, or the LPG on 0, 0 if a closer one\
            can't be found.

        :param machine_vertex: the machine vertex to locate the nearest LPG to
        :param machine_lpgs: dict of gatherers by chip placed on
        :param machine: the SpiNNaker machine object
        :type machine: ~spinn_machine.Machine
        :param placements: the placements object
        :return: the local LPG
        :raise ConfigurationException: if a local gatherer cannot be found
        """

        # locate location of vertex in machine
        placement = placements.get_placement_of_vertex(machine_vertex)
        chip = machine.get_chip_at(placement.x, placement.y)

        # locate closest LPG
        if (chip.nearest_ethernet_x, chip.nearest_ethernet_y) in machine_lpgs:
            return machine_lpgs[
                chip.nearest_ethernet_x, chip.nearest_ethernet_y]

        if (0, 0) in machine_lpgs:
            return machine_lpgs[0, 0]

        # if got through all LPG vertices and not found the right one. go BOOM
        raise ConfigurationException(
            "Cannot find a Live Packet Gatherer from {} for the vertex {}"
            " located {}:{}".format(
                machine_lpgs, machine_vertex, chip.x, chip.y))
