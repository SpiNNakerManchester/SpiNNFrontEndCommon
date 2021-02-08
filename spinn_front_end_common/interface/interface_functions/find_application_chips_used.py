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
from spinn_front_end_common.utilities.helpful_functions import (
    find_executable_start_type)
from spinn_front_end_common.utilities.utility_objs import ExecutableType


class FindApplicationChipsUsed(object):
    """ Builds a set of stats on how many chips were used for application\
        cores.
    """

    def __call__(self, placements):
        """ Finds how many application chips there were and the cost on \
            each chip

        :param ~pacman.model.placements.Placements placements: placements
        :return: a tuple with 4 elements.

            1. how many chips were used
            2. the max application cores on any given chip
            3. the lowest number of application cores on any given chip
            4. the average number of application cores on any given chip

        :rtype: tuple(int,int,int,float)
        """
        chips_used = defaultdict(int)
        for placement in placements:
            # find binary type if applicable
            binary_start_type = find_executable_start_type(placement.vertex)
            if binary_start_type != ExecutableType.SYSTEM:
                chips_used[placement.x, placement.y] += 1

        low = sys.maxsize
        high = 0
        total = 0
        n_chips_used = len(chips_used)

        for key in chips_used:
            if chips_used[key] < low:
                low = chips_used[key]
            if chips_used[key] > high:
                high = chips_used[key]
            total += chips_used[key]
        average = total / n_chips_used
        return n_chips_used, high, low, average
