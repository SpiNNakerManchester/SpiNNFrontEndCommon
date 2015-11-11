# pacman imports
from pacman.model.constraints.key_allocator_constraints\
    .key_allocator_contiguous_range_constraint \
    import KeyAllocatorContiguousRangeContraint


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

    def get_outgoing_edge_constraints(self):
        """ Returns constraints for contiguous keys
        :return:
        """
        # Keep track of the first partitioned edge
        constraints = list()
        constraints.append(KeyAllocatorContiguousRangeContraint())
        return constraints
