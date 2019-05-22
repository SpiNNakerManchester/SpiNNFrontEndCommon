from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinn_front_end_common.utilities.utility_objs import ExecutableType


class FindApplicationChipsUsed(object):

    def __call__(self, placements):
        chips_used = set()
        for placement in placements:
            if (isinstance(placement.vertex, AbstractHasAssociatedBinary) and
                    placement.vertex.get_binary_start_type() !=
                    ExecutableType.SYSTEM):
                chips_used.add((placement.x, placement.y))
        return len(chips_used)
