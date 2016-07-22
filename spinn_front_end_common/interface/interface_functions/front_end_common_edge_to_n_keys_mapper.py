# pacman imports
from pacman.model.routing_info.\
    dict_based_machine_partition_n_keys_map import \
    DictBasedMachinePartitionNKeysMap

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

    def __call__(self, machine_graph, application_graph=None,
                 graph_mapper=None):

        # Generate an n_keys map for the graph and add constraints
        n_keys_map = DictBasedMachinePartitionNKeysMap()

        # generate progress bar
        progress_bar = ProgressBar(
            len(machine_graph.vertices),
            "Deducing edge to number of keys map")

        if application_graph is not None and graph_mapper is not None:

            # iterate over each partition in the graph
            for vertex in application_graph.vertices:
                partitions = application_graph.\
                    get_outgoing_edge_partitions_starting_at_vertex(
                        vertex)
                for partition in partitions:
                    added_constraints = False
                    constraints = self._process_application_partition(
                        partition, n_keys_map, partition.identifier,
                        graph_mapper, application_graph)
                    if not added_constraints:
                        partition.add_constraints(constraints)
                    else:
                        self._check_constraints_equal(
                            constraints, partition.constraints)
                progress_bar.update()
            progress_bar.end()
        else:
            for vertex in machine_graph.vertices:
                partitions = machine_graph.\
                    get_outgoing_edge_partitions_starting_at_vertex(
                        vertex)
                for partition in partitions:
                    added_constraints = False
                    constraints = self._process_machine_partition(
                        partition, n_keys_map, partition.identifier,
                        machine_graph)
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
    def _process_application_partition(
            partition, n_keys_map, partition_id, graph_mapper,
            application_graph):
        vertex_slice = graph_mapper.get_slice(
            partition.pre_vertex)
        vertex = graph_mapper.get_application_vertex(
            partition.pre_vertex)

        if not isinstance(vertex, AbstractProvidesNKeysForPartition):
            n_keys_map.set_n_keys_for_partition(
                partition, vertex_slice.n_atoms)
        else:
            n_keys_map.set_n_keys_for_partition(
                partition,
                vertex.get_n_keys_for_partition(
                    partition, graph_mapper))

        constraints = list()
        if isinstance(vertex,
                      AbstractProvidesOutgoingPartitionConstraints):
            constraints.extend(
                vertex.get_outgoing_partition_constraints(
                    partition, graph_mapper))
        for edge in partition.edges:
            app_edge = graph_mapper.get_application_edge(edge)
            if isinstance(app_edge.post_vertex,
                          AbstractProvidesIncomingPartitionConstraints):
                constraints.extend(
                    app_edge.post_vertex.get_incoming_partition_constraints(
                        partition, graph_mapper))
        constraints.extend(partition.constraints)
        return constraints

    @staticmethod
    def _process_machine_partition(
            partition, n_keys_map, partition_id, machine_graph):

        if not isinstance(partition.pre_vertex,
                          AbstractProvidesNKeysForPartition):
            n_keys_map.set_n_keys_for_partition(partition, 1)
        else:
            n_keys_map.set_n_keys_for_partition(
                partition,
                partition.pre_vertex.get_n_keys_for_partition(
                    partition, None))

        constraints = list()
        if isinstance(partition.pre_vertex,
                      AbstractProvidesOutgoingPartitionConstraints):
            constraints.extend(
                partition.pre_vertex.get_outgoing_partition_constraints(
                    partition, None))

        for edge in partition.edges:
            if isinstance(edge.post_vertex,
                          AbstractProvidesIncomingPartitionConstraints):
                constraints.extend(
                    edge.post_vertex.get_incoming_partition_constraints(
                        partition, None))
        constraints.extend(partition.constraints)

        return constraints
