"""
AbstractOutgoingEdgeSameContiguousKeysRestrictor
"""

# spinn_front_end_common imports
from spinn_front_end_common.abstract_models\
    .abstract_provides_outgoing_edge_constraints \
    import AbstractProvidesOutgoingEdgeConstraints

# pacman imports
from pacman.model.constraints.key_allocator_constraints\
    .key_allocator_contiguous_range_constraint \
    import KeyAllocatorContiguousRangeContraint


class AbstractOutgoingEdgeSameContiguousKeysRestrictor(
        AbstractProvidesOutgoingEdgeConstraints):
    """ Ensures that the edges going out of this vertex are all given the same
        keys, and that those keys are contiguous
    """

    def __init__(self):

        AbstractProvidesOutgoingEdgeConstraints.__init__(self)

    def get_outgoing_edge_constraints(self, partitioned_edge, graph_mapper):
        """
        returns any outgoing contraints for edges
        :param partitioned_edge:
        :param graph_mapper:
        :return: iterable of constraints
        """

        # All populations that use this data spec need to make sure that
        # all edges out of each sub population have keys that are contiguous
        constraints = list()
        constraints.append(KeyAllocatorContiguousRangeContraint())
        return constraints