# Copyright (c) 2019-2020 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

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

        low = sys.maxsize
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
