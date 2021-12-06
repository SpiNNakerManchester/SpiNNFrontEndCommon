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
from pacman.model.graphs.machine import MachineEdge
from spinn_front_end_common.utilities.exceptions import ConfigurationException


def insert_edges_to_live_packet_gatherers(
        live_packet_gatherer_parameters, placements,
        live_packet_gatherers_to_vertex_mapping, machine,
        machine_graph, application_graph=None, n_keys_map=None):
    """
        Add edges from the recorded vertices to the local Live PacketGatherers.

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
            dict(LivePacketGatherParameters,
            tuple(LivePacketGather or None,
            dict(tuple(int,int),LivePacketGatherMachineVertex)))
        :param ~spinn_machine.Machine machine: the SpiNNaker machine
        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
            the machine graph
        :param application_graph: the application graph
        :type application_graph:
            ~pacman.model.graphs.application.ApplicationGraph
        :param n_keys_map: key map
        :type n_keys_map:
            ~pacman.model.routing_info.DictBasedMachinePartitionNKeysMap
    """
    inserter = _InsertEdgesToLivePacketGatherers(
        placements, live_packet_gatherers_to_vertex_mapping, machine)
    inserter._run(live_packet_gatherer_parameters, machine_graph,
                  application_graph, n_keys_map)


class _InsertEdgesToLivePacketGatherers(object):
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

    def __init__(self, placements, live_packet_gatherers_to_vertex_mapping,
                 machine):
        """

        :param ~pacman.model.placements.Placements placements:
            the placements object
        :param live_packet_gatherers_to_vertex_mapping:
            the mapping of LPG parameters and the machine vertices associated
            with it
        :type live_packet_gatherers_to_vertex_mapping:
            dict(LivePacketGatherParameters,
            tuple(LivePacketGather or None,
            dict(tuple(int,int),LivePacketGatherMachineVertex)))
        :param ~spinn_machine.Machine machine: the SpiNNaker machine
        """
        # These are all contextual, and unmodified by this algorithm
        self._lpg_to_vertex = live_packet_gatherers_to_vertex_mapping
        self._machine = machine
        self._placements = placements

    def _run(self, live_packet_gatherer_parameters,
             machine_graph, application_graph=None, n_keys_map=None):
        """
        :param live_packet_gatherer_parameters: the set of parameters
        :type live_packet_gatherer_parameters:
            dict(LivePacketGatherParameters,
            list(tuple(~pacman.model.graphs.AbstractVertex, list(str))))
        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
            the machine graph
        :param application_graph: the application graph
        :type application_graph:
            ~pacman.model.graphs.application.ApplicationGraph
        :param n_keys_map: key map
        :type n_keys_map:
            ~pacman.model.routing_info.DictBasedMachinePartitionNKeysMap
        """
        # pylint: disable=too-many-arguments, attribute-defined-outside-init

        progress = ProgressBar(
            live_packet_gatherer_parameters,
            string_describing_what_being_progressed=(
                "Adding edges to the machine graph between the vertices to "
                "which live output has been requested and its local Live "
                "Packet Gatherer"))

        if application_graph.n_vertices == 0:
            for lpg_params in progress.over(live_packet_gatherer_parameters):
                # locate vertices to connect to a LPG with these params
                for vertex, p_ids in live_packet_gatherer_parameters[
                        lpg_params]:
                    self._connect_lpg_vertex_in_machine_graph(
                        machine_graph, vertex, lpg_params, p_ids, n_keys_map)
        else:
            for lpg_params in progress.over(live_packet_gatherer_parameters):
                # locate vertices to connect to a LPG with these params
                for vertex, p_ids in live_packet_gatherer_parameters[
                        lpg_params]:
                    self._connect_lpg_vertex_in_application_graph(
                        application_graph, machine_graph, vertex, lpg_params,
                        p_ids, n_keys_map)

    @staticmethod
    def _process_partitions(partitions, n_keys_map):
        """ helper method to add to n keys map

        :param set partitions: the partitions to add keys for
        :param ~.DictBasedMachinePartitionNKeysMap n_keys_map: the key map
        :return:
        """
        for partition in partitions:
            n_keys = partition.pre_vertex.get_n_keys_for_partition(
                partition)
            n_keys_map.set_n_keys_for_partition(partition, n_keys)

    def _connect_lpg_vertex_in_application_graph(
            self, app_graph, m_graph, app_vertex, lpg_params, p_ids,
            n_keys_map):
        """
        :param ~.ApplicationGraph app_graph:
        :param ~.MachineGraph m_graph:
        :param ~.ApplicationVertex app_vertex:
        :param LivePacketGatherParameters lpg_params:
        :param list(str) p_ids:
        :param ~.DictBasedMachinePartitionNKeysMap n_keys_map:
        """
        if not app_vertex.machine_vertices or not p_ids:
            return

        m_partitions = set()

        _, machine_lpgs = self._lpg_to_vertex[lpg_params]
        for p_id in p_ids:
            part = app_graph.get_outgoing_edge_partition_starting_at_vertex(
                app_vertex, p_id)
            app_edge = next(iter(part.edges))

            m_vertices = app_vertex.splitter.get_out_going_vertices(
                app_edge, part)
            for vertex in m_vertices.keys():
                lpg = self._find_closest_live_packet_gatherer(
                    vertex, machine_lpgs)
                machine_edge = MachineEdge(vertex, lpg, app_edge=app_edge)
                m_graph.add_edge(machine_edge, p_id)
                lpg.add_incoming_edge(machine_edge)

                # add to n_keys_map if needed
                if n_keys_map:
                    m_partitions.add(m_graph.get_outgoing_partition_for_edge(
                        machine_edge))

        self._process_partitions(m_partitions, n_keys_map)

    def _connect_lpg_vertex_in_machine_graph(
            self, m_graph, m_vertex, lpg_params, p_ids, n_keys_map):
        """
        :param ~.MachineGraph m_graph:
        :param ~.MachineVertex m_vertex:
        :param LivePacketGatherParameters lpg_params:
        :param list(str) p_ids:
        :param ~.DictBasedMachinePartitionNKeysMap n_keys_map:
        """
        # Find all Live Gatherer machine vertices
        machine_lpgs = self._lpg_to_vertex[lpg_params][1]
        lpg = self._find_closest_live_packet_gatherer(m_vertex, machine_lpgs)
        partitions = set()

        # add edges between the closest LPG and the vertex
        for partition_id in p_ids:
            edge = MachineEdge(m_vertex, lpg)
            m_graph.add_edge(edge, partition_id)
            # add to n_keys_map if needed
            if n_keys_map:
                partitions.add(m_graph.get_outgoing_partition_for_edge(edge))
        self._process_partitions(partitions, n_keys_map)

    def _find_closest_live_packet_gatherer(self, m_vertex, machine_lpgs):
        """ Locates the LPG on the nearest Ethernet-connected chip to the\
            machine vertex in question, or the LPG on 0, 0 if a closer one\
            can't be found.

        :param ~.MachineVertex m_vertex:
            the machine vertex to locate the nearest LPG to
        :param dict(tuple(int,int),LivePacketGatherMachineVertex) machine_lpgs:
            the machine LPGs to search with their associated placements
        :return: the local LPG
        :rtype: LivePacketGatherMachineVertex
        :raise ConfigurationException: if a local gatherer cannot be found
        """
        # locate location of vertex in machine
        placement = self._placements.get_placement_of_vertex(m_vertex)
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
                machine_lpgs, m_vertex, chip.x, chip.y))
