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
from pacman.model.routing_info import DictBasedMachinePartitionNKeysMap
from spinn_front_end_common.utilities.exceptions import ConfigurationException


class EdgeToNKeysMapper(object):
    """ Works out the number of keys needed for each edge.
    """

    __slots__ = []

    PROG_BAR_NAME = (
        "Getting number of keys required by each edge using application graph")
    ERROR_MSG = (
        "A machine graph is required for this mapper. Please choose and try "
        "again")

    def __call__(self, machine_graph):
        """
        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
        :rtype: ~pacman.model.routing_info.DictBasedMachinePartitionNKeysMap
        :raises ConfigurationException: If no graph is available
        """
        if machine_graph is None:
            raise ConfigurationException(self.ERROR_MSG)

        # Generate an n_keys map for the graph and add constraints
        n_keys_map = DictBasedMachinePartitionNKeysMap()

        # generate progress bar
        progress = ProgressBar(machine_graph.n_vertices, self.PROG_BAR_NAME)

        # iterate over each partition in the graph
        for vertex in progress.over(machine_graph.vertices):
            for partition in machine_graph.\
                    get_multicast_edge_partitions_starting_at_vertex(vertex):
                n_keys = partition.pre_vertex.get_n_keys_for_partition(
                    partition)
                n_keys_map.set_n_keys_for_partition(partition, n_keys)

        return n_keys_map
