# pacman imports
from pacman.model.routing_info.\
    dict_based_partitioned_partition_n_keys_map import \
    DictBasedPartitionedPartitionNKeysMap

# spinnMachine imports
from spinn_machine.utilities.progress_bar import ProgressBar

# front end common imports
from spinn_front_end_common.abstract_models.\
    abstract_provides_incoming_partition_constraints import \
    AbstractProvidesIncomingPartitionConstraints
from spinn_front_end_common.abstract_models.\
    abstract_provides_n_keys_for_partition import \
    AbstractProvidesNKeysForPartition
from spinn_front_end_common.abstract_models.\
    abstract_provides_outgoing_partition_constraints import \
    AbstractProvidesOutgoingPartitionConstraints
from spinn_front_end_common.utilities import exceptions


class FrontEndCommonEdgeToNKeysMapper(object):
    """ Works out the number of keys needed for each edge
    """

    def __call__(self, partitioned_graph, partitionable_graph=None,
                 graph_mapper=None):

        # Generate an n_keys map for the graph and add constraints
        n_keys_map = DictBasedPartitionedPartitionNKeysMap()

        # generate progress bar
        progress_bar = ProgressBar(
            len(partitioned_graph.subvertices),
            "Deducing edge to number of keys map")

        # contains a partitionable vertex
        if partitionable_graph is not None and graph_mapper is not None:
            # iterate over each partition in the partitioned graph
            for vertex in partitioned_graph.subvertices:
                partitions = \
                    partitioned_graph.outgoing_edges_partitions_from_vertex(
                        vertex)
                for partition_id in partitions:
                    partition = partitions[partition_id]
                    added_constraints = False
                    constraints = self._process_partitionable_partition(
                        partition, n_keys_map, partition_id, graph_mapper,
                        partitionable_graph)
                    if not added_constraints:
                        partition.add_constraints(constraints)
                    else:
                        self._check_constraints_equal(
                            constraints, partition.constraints)
                progress_bar.update()
            progress_bar.end()
        else:
            for vertex in partitioned_graph.subvertices:
                partitions = \
                    partitioned_graph.outgoing_edges_partitions_from_vertex(
                        vertex)
                for partition_id in partitions:
                    partition = partitions[partition_id]
                    added_constraints = False
                    constraints = self._process_partitioned_partition(
                        partition, n_keys_map, partition_id, partitioned_graph)
                    if not added_constraints:
                        partition.add_constraints(constraints)
                    else:
                        self._check_constraints_equal(
                            constraints, partition.constraints)
                progress_bar.update()
            progress_bar.end()

        return {'n_keys_map': n_keys_map}

    @staticmethod
    def _check_constraints_equal(constraints, stored_constraints):
        """

        :param constraints:
        :param stored_constraints:
        :return:
        """
        for constraint in constraints:
            if constraint not in stored_constraints:
                raise exceptions.ConfigurationException(
                    "Two edges within the same partition have different "
                    "constraints. This is deemed an error. Please fix and "
                    "try again")

    @staticmethod
    def _process_partitionable_partition(
            partition, n_keys_map, partition_id, graph_mapper,
            partitionable_graph):
        partitioned_edge = partition.edges[0]
        vertex_slice = graph_mapper.get_subvertex_slice(
            partitioned_edge.pre_subvertex)
        edge = graph_mapper.get_partitionable_edge_from_partitioned_edge(
            partitioned_edge)

        if not isinstance(edge.pre_vertex, AbstractProvidesNKeysForPartition):
            n_keys_map.set_n_keys_for_partition(
                partition, vertex_slice.n_atoms)
        else:
            n_keys_map.set_n_keys_for_partition(
                partition,
                edge.pre_vertex.get_n_keys_for_partition(
                    partition, graph_mapper))

        constraints = list()
        if isinstance(edge.pre_vertex,
                      AbstractProvidesOutgoingPartitionConstraints):
            constraints.extend(
                edge.pre_vertex.get_outgoing_partition_constraints(
                    partition, graph_mapper))
        if isinstance(edge.post_vertex,
                      AbstractProvidesIncomingPartitionConstraints):
            constraints.extend(
                edge.post_vertex.get_incoming_partition_constraints(
                    partition, graph_mapper))
        constraints.extend(
            partitionable_graph.partition_from_vertex(
                edge.pre_vertex, partition_id).constraints)
        return constraints

    @staticmethod
    def _process_partitioned_partition(
            partition, n_keys_map, partition_id, partitioned_graph):
        edge = partition.edges[0]

        if not isinstance(edge.pre_subvertex,
                          AbstractProvidesNKeysForPartition):
            n_keys_map.set_n_keys_for_partition(partition, 1)
        else:
            n_keys_map.set_n_keys_for_partition(
                partition,
                edge.pre_subvertex.get_n_keys_for_partition(
                    partition, None))

        constraints = list()
        if isinstance(edge.pre_subvertex,
                      AbstractProvidesOutgoingPartitionConstraints):
            constraints.extend(
                edge.pre_subvertex.get_outgoing_partition_constraints(
                    partition, None))
        if isinstance(edge.post_subvertex,
                      AbstractProvidesIncomingPartitionConstraints):
            constraints.extend(
                edge.post_subvertex.get_incoming_partition_constraints(
                    partition, None))
        constraints.extend(
            partitioned_graph.partition_from_vertex(
                edge.pre_subvertex, partition_id).constraints)

        return constraints
