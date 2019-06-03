from collections import defaultdict

import sys

from spinn_front_end_common.utilities.helpful_functions import \
    find_executable_start_type
from spinn_front_end_common.utilities.utility_objs import ExecutableType


class FindApplicationChipsUsed(object):

    def __call__(self, placements, graph_mapper=None):
        chips_used = defaultdict(int)
        for placement in placements:
            # find binary type if applicable
            binary_start_type = find_executable_start_type(
                placement.vertex, graph_mapper)

            if binary_start_type != ExecutableType.SYSTEM:
                chips_used[(placement.x, placement.y)] += 1

        low = sys.maxint
        high = 0
        average = 0

        for key in chips_used:
            if chips_used[key] < low:
                low = chips_used[key]
            if chips_used[key] > high:
                high = chips_used[key]
            average += chips_used[key]
        average = average / len(chips_used.keys())
        return len(chips_used.keys()), high, low, average
