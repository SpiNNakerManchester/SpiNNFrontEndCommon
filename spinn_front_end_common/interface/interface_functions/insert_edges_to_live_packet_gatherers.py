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
            machine_graph, application_graph=None):
        """
        :param live_packet_gatherer_parameters: the set of parameters
        :param placements: the placements object
        :param live_packet_gatherers_to_vertex_mapping:\
            the mapping of LPG parameters and the machine vertices associated\
            with it
        :param machine: the SpiNNaker machine
        :param machine_graph: the machine graph
        :param application_graph: the application graph
        :rtype: None
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

        if application_graph is None:
            for lpg_params in progress.over(live_packet_gatherer_parameters):
                # locate vertices to connect to a LPG with these params
                for vertex in live_packet_gatherer_parameters[lpg_params]:
                    self._connect_lpg_vertex_in_mach_graph(
                        machine_graph, vertex, lpg_params)
        else:
            for lpg_params in progress.over(live_packet_gatherer_parameters):
                # locate vertices to connect to a LPG with these params
                for vertex in live_packet_gatherer_parameters[lpg_params]:
                    self._connect_lpg_vertex_in_app_graph(
                        application_graph, machine_graph, vertex, lpg_params)

    def _connect_lpg_vertex_in_app_graph(
            self, app_graph, m_graph, app_vertex, lpg_params):
        # pylint: disable=too-many-arguments

        # Find all Live Gatherer machine vertices
        m_lpgs = self._lpg_to_vertex[lpg_params]

        # flag for ensuring we don't add the edge to the app
        # graph many times
        app_edge = None

        # iterate through the associated machine vertices
        for machine_vertex in app_vertex.machine_vertices:
            machine_lpg = self._find_closest_live_packet_gatherer(
                machine_vertex, m_lpgs)

            # locate app app_vertex for LPG
            lpg_app_vertex = machine_lpg.app_vertex

            # if not built the app edge, add the app edge now
            if app_edge is None:
                app_edge = ApplicationEdge(app_vertex, lpg_app_vertex)
                app_graph.add_edge(app_edge, lpg_params.partition_id)

            # add a edge between the closest LPG and the app_vertex
            machine_edge = app_edge.create_machine_edge(
                machine_vertex, machine_lpg, None)
            m_graph.add_edge(machine_edge, lpg_params.partition_id)

            # add mapping between the app edge and the machine edge
            app_edge.remember_associated_machine_edge(machine_edge)

    def _connect_lpg_vertex_in_mach_graph(
            self, m_graph, vertex, lpg_params):
        # Find all Live Gatherer machine vertices
        lpg = self._find_closest_live_packet_gatherer(
            vertex, self._lpg_to_vertex[lpg_params])

        # add a edge between the closest LPG and the vertex
        m_graph.add_edge(MachineEdge(vertex, lpg), lpg_params.partition_id)

    def _find_closest_live_packet_gatherer(self, machine_vertex, machine_lpgs):
        """ Locates the LPG on the nearest Ethernet-connected chip to the\
            machine vertex in question, or the LPG on 0, 0 if a closer one\
            can't be found.

        :param machine_vertex: the machine vertex to locate the nearest LPG to
        :param machine_lpgs: dict of gatherers by chip placed on
        :return: the local LPG
        :raise ConfigurationException: if a local gatherer cannot be found
        """
        # locate location of vertex in machine
        placement = self._placements.get_placement_of_vertex(machine_vertex)
        chip = self._machine.get_chip_at(placement.x, placement.y)

        # locate closest LPG
        chip_key = (chip.nearest_ethernet_x, chip.nearest_ethernet_y)
        if chip_key in machine_lpgs:
            return machine_lpgs[chip_key]

        # Fallback to the root (better than total failure)
        if (0, 0) in machine_lpgs:
            return machine_lpgs[0, 0]

        # if got through all LPG vertices and not found the right one. go BOOM
        raise ConfigurationException(
            "Cannot find a Live Packet Gatherer from {} for the vertex {}"
            " located on {}:{}".format(
                machine_lpgs, machine_vertex, chip.x, chip.y))
