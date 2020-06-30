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


class BitFieldSummary(object):
    """ Summary description of generated bitfields.
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
