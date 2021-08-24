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
from pacman.model.constraints.key_allocator_constraints import (
    AbstractKeyAllocatorConstraint)
from spinn_front_end_common.abstract_models import (
    AbstractProvidesOutgoingPartitionConstraints,
    AbstractProvidesIncomingPartitionConstraints)


class ProcessPartitionConstraints(object):
    """ Adds constraints to partitions if the vertices at either end of the\
        partition request it.
    """

    def __call__(self, machine_graph):
        """
        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
        """
        # generate progress bar
        progress = ProgressBar(
            machine_graph.n_vertices,
            "Getting constraints for machine graph")

        # iterate over each partition in the graph
        for vertex in progress.over(machine_graph.vertices):
            for partition in machine_graph.\
                    get_multicast_edge_partitions_starting_at_vertex(
                        vertex):
                self._process_partition(partition)

    @staticmethod
    def _process_partition(partition):
        """
        Process the partition by checking the pre_vertex and post vertices

        Note: The machine level is checked first and only only if that does
            not provide the api the app vertex is check next
        :param ~.OutgoingEdgePartition partition:
        """
        vertex = partition.pre_vertex
        # add_vertex_constraints
        for constraint in vertex.constraints:
            if isinstance(constraint, AbstractKeyAllocatorConstraint):
                partition.add_constraint(constraint)

        # call get_outgoing_partition_constraints method on pre_vertex
        if isinstance(vertex, AbstractProvidesOutgoingPartitionConstraints):
            partition.add_constraints(
                vertex.get_outgoing_partition_constraints(partition))
        else:
            vertex = vertex.app_vertex
            if isinstance(vertex,
                          AbstractProvidesOutgoingPartitionConstraints):
                partition.add_constraints(
                    vertex.get_outgoing_partition_constraints(partition))

        # call get_incoming_partition_constraints on post_vertex
        for edge in partition.edges:
            post_vertex = edge.post_vertex
            if isinstance(post_vertex,
                          AbstractProvidesIncomingPartitionConstraints):
                partition.add_constraints(
                    post_vertex.get_incoming_partition_constraints(partition))
            elif edge.app_edge:
                post_vertex = edge.app_edge.post_vertex
                if isinstance(post_vertex,
                              AbstractProvidesIncomingPartitionConstraints):
                    partition.add_constraints(
                        post_vertex.get_incoming_partition_constraints(
                            partition))
