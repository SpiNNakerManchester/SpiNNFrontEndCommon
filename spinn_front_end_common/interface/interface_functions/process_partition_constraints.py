from spinn_utilities.progress_bar import ProgressBar
from pacman.model.graphs.common import EdgeTrafficType
from spinn_front_end_common.abstract_models import (
    AbstractProvidesOutgoingPartitionConstraints,
    AbstractProvidesIncomingPartitionConstraints)
from spinn_front_end_common.utilities.exceptions import ConfigurationException


class ProcessPartitionConstraints(object):
    def __call__(self, machine_graph=None, application_graph=None,
                 graph_mapper=None):

        if machine_graph is None:
            raise ConfigurationException(
                "A machine graph is required for this mapper. "
                "Please choose and try again")
        if (application_graph is None) != (graph_mapper is None):
            raise ConfigurationException(
                "Can only do one graph. semantically doing 2 graphs makes no "
                "sense. Please choose and try again")

        if application_graph is not None:
            # generate progress bar
            progress = ProgressBar(
                machine_graph.n_vertices,
                "Getting constraints for application graph")

            # iterate over each partition in the graph
            for vertex in progress.over(machine_graph.vertices):
                partitions = machine_graph.\
                    get_outgoing_edge_partitions_starting_at_vertex(
                        vertex)
                for partition in partitions:
                    if partition.traffic_type == EdgeTrafficType.MULTICAST:
                        self._process_application_partition(
                            partition, graph_mapper)
        else:
            # generate progress bar
            progress = ProgressBar(
                machine_graph.n_vertices,
                "Getting constraints for machine graph")

            for vertex in progress.over(machine_graph.vertices):
                partitions = machine_graph.\
                    get_outgoing_edge_partitions_starting_at_vertex(
                        vertex)
                for partition in partitions:
                    if partition.traffic_type == EdgeTrafficType.MULTICAST:
                        self._process_machine_partition(partition)

    @staticmethod
    def _process_application_partition(partition, graph_mapper):
        vertex = graph_mapper.get_application_vertex(
            partition.pre_vertex)
        if isinstance(vertex,
                      AbstractProvidesOutgoingPartitionConstraints):
            partition.add_constraints(
                vertex.get_outgoing_partition_constraints(partition))
        for edge in partition.edges:
            if edge.label is not "spinnakear":
                app_edge = graph_mapper.get_application_edge(edge)
                if isinstance(app_edge.post_vertex,
                              AbstractProvidesIncomingPartitionConstraints):
                    partition.add_constraints(
                        app_edge.post_vertex.get_incoming_partition_constraints(
                            partition))

    @staticmethod
    def _process_machine_partition(partition):
        if isinstance(partition.pre_vertex,
                      AbstractProvidesOutgoingPartitionConstraints):
            partition.add_constraints(
                partition.pre_vertex.get_outgoing_partition_constraints(
                    partition))
        for edge in partition.edges:
            if isinstance(edge.post_vertex,
                          AbstractProvidesIncomingPartitionConstraints):
                partition.add_constraints(
                    edge.post_vertex.get_incoming_partition_constraints(
                        partition))
