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
from pacman.model.graphs.common import EdgeTrafficType
from pacman.model.routing_info import DictBasedMachinePartitionNKeysMap
from spinn_front_end_common.abstract_models import (
    AbstractProvidesNKeysForPartition)
from spinn_front_end_common.utilities.exceptions import ConfigurationException


class EdgeToNKeysMapper(object):
    """ Works out the number of keys needed for each edge.
    """

    __slots__ = []

    def __call__(self, machine_graph=None, graph_mapper=None):

        if machine_graph is None:
            raise ConfigurationException(
                "A machine graph is required for this mapper. "
                "Please choose and try again")

        if graph_mapper is not None:
            return self._allocate_by_app_graph_simple(
                machine_graph, graph_mapper)
        else:
            return self._allocate_by_machine_graph_only(machine_graph)

    def _allocate_by_app_graph_simple(
            self, machine_graph, graph_mapper):
        # Generate an n_keys map for the graph and add constraints
        n_keys_map = DictBasedMachinePartitionNKeysMap()

        # generate progress bar
        progress = ProgressBar(
            machine_graph.n_vertices,
            "Getting number of keys required by each edge using "
            "application graph")

        # iterate over each partition in the graph
        for vertex in progress.over(machine_graph.vertices):
            partitions = machine_graph.\
                get_outgoing_edge_partitions_starting_at_vertex(
                    vertex)
            for partition in partitions:
                if partition.traffic_type == EdgeTrafficType.MULTICAST:
                    self._process_application_partition(
                        partition, n_keys_map, graph_mapper)

        return n_keys_map

    def _allocate_by_machine_graph_only(self, machine_graph):
        # Generate an n_keys map for the graph and add constraints
        n_keys_map = DictBasedMachinePartitionNKeysMap()

        # generate progress bar
        progress = ProgressBar(
            machine_graph.n_vertices,
            "Getting number of keys required by each edge using "
            "machine graph")

        for vertex in progress.over(machine_graph.vertices):
            partitions = machine_graph.\
                get_outgoing_edge_partitions_starting_at_vertex(
                    vertex)
            for partition in partitions:
                if partition.traffic_type == EdgeTrafficType.MULTICAST:
                    self._process_machine_partition(partition, n_keys_map)

        return n_keys_map

    @staticmethod
    def _process_application_partition(partition, n_keys_map, graph_mapper):
        vertex_slice = graph_mapper.get_slice(
            partition.pre_vertex)
        vertex = graph_mapper.get_application_vertex(
            partition.pre_vertex)

        if isinstance(vertex, AbstractProvidesNKeysForPartition):
            n_keys = vertex.get_n_keys_for_partition(partition, graph_mapper)
        else:
            n_keys = vertex_slice.n_atoms
        n_keys_map.set_n_keys_for_partition(partition, n_keys)

    @staticmethod
    def _process_machine_partition(partition, n_keys_map):
        if isinstance(partition.pre_vertex, AbstractProvidesNKeysForPartition):
            n_keys = partition.pre_vertex.get_n_keys_for_partition(
                partition, None)
        else:
            n_keys = 1
        n_keys_map.set_n_keys_for_partition(partition, n_keys)
