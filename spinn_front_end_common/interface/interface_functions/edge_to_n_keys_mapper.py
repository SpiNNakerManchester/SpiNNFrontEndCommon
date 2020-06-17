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
                    self.process_partition(partition, n_keys_map)

        return n_keys_map

    @staticmethod
    def process_partition(partition, n_keys_map):
        """
        :param ~pacman.model.graphs.OutgoingEdgePartition partition:
        :param n_keys_map:
        :type n_keys_map:
            ~pacman.model.routing_info.DictBasedMachinePartitionNKeysMap
        """
        pre_vertex = partition.pre_vertex
        if pre_vertex.app_vertex:
            specific_pre_vertex = pre_vertex.app_vertex
        else:
            specific_pre_vertex = pre_vertex

        if isinstance(specific_pre_vertex, AbstractProvidesNKeysForPartition):
            n_keys = specific_pre_vertex.get_n_keys_for_partition(partition)
        else:
            n_keys = pre_vertex.vertex_slice.n_atoms
        n_keys_map.set_n_keys_for_partition(partition, n_keys)
