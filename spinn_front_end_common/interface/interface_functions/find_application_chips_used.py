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
from typing import Dict, Tuple
from spinn_utilities.typing.coords import XY
from spinnman.model.enums import ExecutableType
from pacman.model.placements import Placements
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary


class FindApplicationChipsUsed(object):
    """
    Builds a set of stats on how many chips were used for application cores.
    """

    def __call__(self, placements: Placements) -> Tuple[int, int, int, float]:
        """
        Finds how many application chips there were and the cost on each chip

        :param placements: placements
        :return: a tuple with 4 elements.

            1. how many chips were used
            2. the max application cores on any given chip
            3. the lowest number of application cores on any given chip
            4. the average number of application cores on any given chip
        """
        chips_used = self._get_chips_used(placements)

        low = sys.maxsize
        high = 0
        total = 0
        n_chips_used = len(chips_used)

        for count in chips_used.values():
            if count < low:
                low = count
            if count > high:
                high = count
            total += count
        average = total / n_chips_used
        return n_chips_used, high, low, average

    def _get_chips_used(self, placements: Placements) -> Dict[XY, int]:
        chips_used: Dict[XY, int] = defaultdict(int)
        for placement in placements:
            # find binary type if applicable
            binary_start_type = None
            if isinstance(placement.vertex, AbstractHasAssociatedBinary):
                binary_start_type = placement.vertex.get_binary_start_type()
            if binary_start_type != ExecutableType.SYSTEM:
                chips_used[placement.x, placement.y] += 1
        return chips_used
