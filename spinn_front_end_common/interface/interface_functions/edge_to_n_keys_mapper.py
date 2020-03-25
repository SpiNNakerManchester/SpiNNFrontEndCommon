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

    :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
    :rtype: ~pacman.model.routing_info.DictBasedMachinePartitionNKeysMap
    :raises: ConfigurationException
    """

    __slots__ = []

    def __call__(self, machine_graph):
        """
        :param ~.MachineGraph machine_graph:
        :rtype: ~.DictBasedMachinePartitionNKeysMap
        :raises: ConfigurationException
        """
        if machine_graph is None:
            raise ConfigurationException(
                "A machine graph is required for this mapper. "
                "Please choose and try again")

        av = None
        for mv in machine_graph.vertices:
            av = mv.app_vertex
            break
        if av is not None:
            return self._allocate_by_app_graph_simple(machine_graph)
        else:
            return self._allocate_by_machine_graph_only(machine_graph)

    def _allocate_by_app_graph_simple(self, machine_graph):
        """
        :param ~.MachineGraph machine_graph:
        :rtype: ~.DictBasedMachinePartitionNKeysMap
        """
        # Generate an n_keys map for the graph and add constraints
        n_keys_map = DictBasedMachinePartitionNKeysMap()

        # generate progress bar
        progress = ProgressBar(
            machine_graph.n_vertices,
            "Getting number of keys required by each edge using "
            "application graph")

        # iterate over each partition in the graph
        for vertex in progress.over(machine_graph.vertices):
            for partition in machine_graph.\
                    get_outgoing_edge_partitions_starting_at_vertex(
                        vertex):
                if partition.traffic_type == EdgeTrafficType.MULTICAST:
                    self._process_application_partition(
                        partition, n_keys_map)

        return n_keys_map

    def _allocate_by_machine_graph_only(self, machine_graph):
        """
        :param ~.MachineGraph machine_graph:
        :rtype: ~.DictBasedMachinePartitionNKeysMap
        """
        # Generate an n_keys map for the graph and add constraints
        n_keys_map = DictBasedMachinePartitionNKeysMap()

        # generate progress bar
        progress = ProgressBar(
            machine_graph.n_vertices,
            "Getting number of keys required by each edge using "
            "machine graph")

        for vertex in progress.over(machine_graph.vertices):
            for partition in machine_graph.\
                    get_outgoing_edge_partitions_starting_at_vertex(
                        vertex):
                if partition.traffic_type == EdgeTrafficType.MULTICAST:
                    self._process_machine_partition(partition, n_keys_map)

        return n_keys_map

    @staticmethod
    def _process_application_partition(partition, n_keys_map):
        """
        :param ~.OutgoingEdgePartition partition:
        :param ~.DictBasedMachinePartitionNKeysMap n_keys_map:
        """
        vertex = partition.pre_vertex.app_vertex

        if isinstance(vertex, AbstractProvidesNKeysForPartition):
            n_keys = vertex.get_n_keys_for_partition(partition)
        else:
            n_keys = partition.pre_vertex.vertex_slice.n_atoms
        n_keys_map.set_n_keys_for_partition(partition, n_keys)

    @staticmethod
    def _process_machine_partition(partition, n_keys_map):
        """
        :param ~.OutgoingEdgePartition partition:
        :param ~.DictBasedMachinePartitionNKeysMap n_keys_map:
        """
        if isinstance(partition.pre_vertex, AbstractProvidesNKeysForPartition):
            n_keys = partition.pre_vertex.get_n_keys_for_partition(partition)
        else:
            n_keys = 1
        n_keys_map.set_n_keys_for_partition(partition, n_keys)
