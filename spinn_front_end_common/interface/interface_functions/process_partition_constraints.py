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
from spinn_front_end_common.abstract_models import (
    AbstractProvidesOutgoingPartitionConstraints,
    AbstractProvidesIncomingPartitionConstraints)


class ProcessPartitionConstraints(object):
    def __call__(self, machine_graph, application_graph=None):
        if application_graph is not None:
            # generate progress bar
            progress = ProgressBar(
                machine_graph.n_vertices,
                "Getting constraints for application graph")

            # iterate over each partition in the graph
            for vertex in progress.over(machine_graph.vertices):
                for partition in machine_graph.\
                        get_outgoing_edge_partitions_starting_at_vertex(
                            vertex):
                    if partition.traffic_type == EdgeTrafficType.MULTICAST:
                        self._process_application_partition(partition)
        else:
            # generate progress bar
            progress = ProgressBar(
                machine_graph.n_vertices,
                "Getting constraints for machine graph")

            for vertex in progress.over(machine_graph.vertices):
                for partition in machine_graph.\
                        get_outgoing_edge_partitions_starting_at_vertex(
                            vertex):
                    if partition.traffic_type == EdgeTrafficType.MULTICAST:
                        self._process_machine_partition(partition)

    @staticmethod
    def _process_application_partition(partition):
        vertex = partition.pre_vertex.app_vertex
        if isinstance(vertex, AbstractProvidesOutgoingPartitionConstraints):
            partition.add_constraints(
                vertex.get_outgoing_partition_constraints(partition))
        for edge in partition.edges:
            post_vertex = edge.app_edge.post_vertex
            if isinstance(post_vertex,
                          AbstractProvidesIncomingPartitionConstraints):
                partition.add_constraints(
                    post_vertex.get_incoming_partition_constraints(partition))

    @staticmethod
    def _process_machine_partition(partition):
        if isinstance(partition.pre_vertex,
                      AbstractProvidesOutgoingPartitionConstraints):
            partition.add_constraints(
                partition.pre_vertex.get_outgoing_partition_constraints(
                    partition))
        for edge in partition.edges:
            post_vertex = edge.post_vertex
            if isinstance(post_vertex,
                          AbstractProvidesIncomingPartitionConstraints):
                partition.add_constraints(
                    post_vertex.get_incoming_partition_constraints(partition))
