from spinn_front_end_common.abstract_models\
    .abstract_provides_outgoing_edge_constraints \
    import AbstractProvidesOutgoingEdgeConstraints
from pacman.model.constraints.key_allocator_constraints\
    .key_allocator_contiguous_range_constraint \
    import KeyAllocatorContiguousRangeContraint
from pacman.model.constraints.key_allocator_constraints\
    .key_allocator_same_keys_constraint \
    import KeyAllocatorSameKeysConstraint


class AbstractOutgoingEdgeSameContiguousKeysRestrictor(
        AbstractProvidesOutgoingEdgeConstraints):
    """ Ensures that the edges going out of this vertex are all given the same
        keys, and that those keys are contiguous
    """

    def __init__(self):

        AbstractProvidesOutgoingEdgeConstraints.__init__(self)

        # The first partitioned edge of this vertex
        self._first_partitioned_edge = None

        # Set of partitioned edges that have already had constraints added,
        # to avoid over processing
        self._seen_partitioned_edges = set()

    def get_outgoing_edge_constraints(self, partitioned_edge):

        # Keep track of the first partitioned edge
        constraints = list()
        if self._first_partitioned_edge is None:
            self._first_partitioned_edge = partitioned_edge
        elif partitioned_edge not in self._seen_partitioned_edges:

            # All populations that use this data spec need to make sure that
            # all edges out of each sub population are given the same keys, and
            # that those keys are contiguous
            constraints.append(KeyAllocatorContiguousRangeContraint())
            constraints.append(KeyAllocatorSameKeysConstraint(
                self._first_partitioned_edge))

        # Avoid processing this edge again
        self._seen_partitioned_edges.add(partitioned_edge)

        return constraints
