# Copyright (c) 2019 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections import defaultdict
import sys
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary


class FindApplicationChipsUsed(object):
    """
    Builds a set of stats on how many chips were used for application cores.
    """

    def __call__(self, placements):
        """
        Finds how many application chips there were and the cost on each chip

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
            binary_start_type = None
            if isinstance(placement.vertex, AbstractHasAssociatedBinary):
                binary_start_type = placement.vertex.get_binary_start_type()
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
