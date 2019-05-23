from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinn_front_end_common.utilities.helpful_functions import \
    find_executable_start_type
from spinn_front_end_common.utilities.utility_objs import ExecutableType


class FindApplicationChipsUsed(object):

    def __call__(self, placements, graph_mapper=None):
        chips_used = set()
        for placement in placements:
            # find binary type if applicable
            binary_start_type = find_executable_start_type(
                placement.vertex, graph_mapper)

            if binary_start_type != ExecutableType.SYSTEM:
                chips_used.add((placement.x, placement.y))
        return len(chips_used)
