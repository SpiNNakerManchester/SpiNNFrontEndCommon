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


class BitFieldSummary(object):
    """
    Summary description of generated bitfields.
    """

    def __init__(
            self, total_merged, max_per_chip, lowest_per_chip, total_to_merge,
            max_to_merge_per_chip, low_to_merge_per_chip,
            average_per_chip_merged, average_per_chip_to_merge):
        """
        :param int total_merged:
        :param int max_per_chip:
        :param int lowest_per_chip:
        :param int total_to_merge:
        :param int max_to_merge_per_chip:
        :param int low_to_merge_per_chip:
        :param float average_per_chip_merged:
        :param float average_per_chip_to_merge:
        """
        self._total_merged = total_merged
        self._max_per_chip = max_per_chip
        self._lowest_per_chip = lowest_per_chip
        self._total_to_merge = total_to_merge
        self._max_to_merge_per_chip = max_to_merge_per_chip
        self._low_to_merge_per_chip = low_to_merge_per_chip
        self._average_per_chip_merged = average_per_chip_merged
        self._average_per_chip_to_merge = average_per_chip_to_merge

    @property
    def total_merged(self):
        """
        :rtype: int
        """
        return self._total_merged

    @property
    def max_per_chip(self):
        """
        :rtype: int
        """
        return self._max_per_chip

    @property
    def lowest_per_chip(self):
        """
        :rtype: int
        """
        return self._lowest_per_chip

    @property
    def total_to_merge(self):
        """
        :rtype: int
        """
        return self._total_to_merge

    @property
    def max_to_merge_per_chip(self):
        """
        :rtype: int
        """
        return self._max_to_merge_per_chip

    @property
    def low_to_merge_per_chip(self):
        """
        :rtype: int
        """
        return self._low_to_merge_per_chip

    @property
    def average_per_chip_merged(self):
        """
        :rtype: float
        """
        return self._average_per_chip_merged

    @property
    def average_per_chip_to_merge(self):
        """
        :rtype: float
        """
        return self._average_per_chip_to_merge
