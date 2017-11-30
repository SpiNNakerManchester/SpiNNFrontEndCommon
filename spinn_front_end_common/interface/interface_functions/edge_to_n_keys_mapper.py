# pacman imports
from pacman.model.graphs.common import EdgeTrafficType
from pacman.model.routing_info \
    import DictBasedMachinePartitionNKeysMap

# utilities imports
from spinn_utilities.progress_bar import ProgressBar

# front end common imports
from spinn_front_end_common.abstract_models import \
    AbstractProvidesIncomingPartitionConstraints, \
    AbstractProvidesNKeysForPartition, \
    AbstractProvidesOutgoingPartitionConstraints
from spinn_front_end_common.utilities.exceptions import ConfigurationException


class EdgeToNKeysMapper(object):
    """ Works out the number of keys needed for each edge
    """

    __slots__ = []

    def __call__(self, machine_graph=None, application_graph=None,
                 graph_mapper=None):
        # Generate an n_keys map for the graph and add constraints
        n_keys_map = DictBasedMachinePartitionNKeysMap()

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
                "Getting number of keys required by each edge using "
                "application graph")

            # iterate over each partition in the graph
            for vertex in progress.over(machine_graph.vertices):
                partitions = machine_graph.\
                    get_outgoing_edge_partitions_starting_at_vertex(
                        vertex)
                for partition in partitions:
                    if partition.traffic_type == EdgeTrafficType.MULTICAST:
                        constraints = self._process_application_partition(
                            partition, n_keys_map, graph_mapper)
                        partition.add_constraints(constraints)

        else:
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
                        constraints = self._process_machine_partition(
                            partition, n_keys_map)
                        partition.add_constraints(constraints)

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

        constraints = list()
        if isinstance(vertex,
                      AbstractProvidesOutgoingPartitionConstraints):
            constraints.extend(
                vertex.get_outgoing_partition_constraints(partition))
        for edge in partition.edges:
            app_edge = graph_mapper.get_application_edge(edge)
            if isinstance(app_edge.post_vertex,
                          AbstractProvidesIncomingPartitionConstraints):
                constraints.extend(
                    app_edge.post_vertex.get_incoming_partition_constraints(
                        partition))
        constraints.extend(partition.constraints)
        return constraints

    @staticmethod
    def _process_machine_partition(partition, n_keys_map):
        if isinstance(partition.pre_vertex, AbstractProvidesNKeysForPartition):
            n_keys = partition.pre_vertex.get_n_keys_for_partition(
                partition, None)
        else:
            n_keys = 1
        n_keys_map.set_n_keys_for_partition(partition, n_keys)

        constraints = list()
        if isinstance(partition.pre_vertex,
                      AbstractProvidesOutgoingPartitionConstraints):
            constraints.extend(
                partition.pre_vertex.get_outgoing_partition_constraints(
                    partition))

        for edge in partition.edges:
            if isinstance(edge.post_vertex,
                          AbstractProvidesIncomingPartitionConstraints):
                constraints.extend(
                    edge.post_vertex.get_incoming_partition_constraints(
                        partition))
        constraints.extend(partition.constraints)

        return constraints
