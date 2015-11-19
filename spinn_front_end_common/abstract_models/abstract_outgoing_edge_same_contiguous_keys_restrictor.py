"""
OutgoingEdgeSameContiguousKeysRestrictor
"""

from pacman.model.constraints.key_allocator_constraints\
    .key_allocator_contiguous_range_constraint \
    import KeyAllocatorContiguousRangeContraint
from pacman.model.constraints.key_allocator_constraints\
    .key_allocator_same_keys_constraint \
    import KeyAllocatorSameKeysConstraint


class OutgoingEdgeSameContiguousKeysRestrictor(object):
    """ Ensures that the edges going out of this vertex are all given the same
        keys, and that those keys are contiguous
    """

    def __init__(self):

        # The first partitioned edge of this population for any subvertex,
        # indexed by the subvertex lo atom
        self._first_partitioned_edge = dict()

        # Set of partitioned edges that have already had constraints added,
        # to avoid over processing
        self._seen_partitioned_edges = set()

    def get_outgoing_edge_constraints(self, partitioned_edge, graph_mapper):
        """
        provides the constraints for outgoing edges for neural applications
        :param partitioned_edge: the partitoned edge to put constraints on
        :param graph_mapper: the graph mapper object
        :return:list of constraints
        """
        # Find the slice of the vertex
        vertex_slice = graph_mapper.get_subvertex_slice(
            partitioned_edge.pre_subvertex)

        # Keep track of the first partitioned edge
        constraints = list()
        if vertex_slice.lo_atom not in self._first_partitioned_edge:
            self._first_partitioned_edge[vertex_slice.lo_atom] = \
                partitioned_edge
        elif partitioned_edge not in self._seen_partitioned_edges:

            # All populations that use this data spec need to make sure that
            # all edges out of each sub population are given the same keys, and
            # that those keys are contiguous
            constraints.append(KeyAllocatorContiguousRangeContraint())
            constraints.append(KeyAllocatorSameKeysConstraint(
                self._first_partitioned_edge[vertex_slice.lo_atom]))

        # Avoid processing this edge again
        self._seen_partitioned_edges.add(partitioned_edge)

        return constraints
