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


class RouterSummary(object):

    __slots__ = [
        "_total_entries",
        "_max_per_chip",
        "_max_defaultable",
        "_max_link",
        "_unqiue_routes",
    ]

    def __init__(self, total_entries, max_per_chip, max_defaultable, max_link,
                 unqiue_routes):

        self._total_entries = total_entries
        self._max_per_chip = max_per_chip
        self._max_defaultable = max_defaultable
        self._max_link = max_link
        self._unqiue_routes = unqiue_routes

    @property
    def total_entries(self):
        """
        :rtype: int
        """
        return self._total_entries

    @property
    def max_per_chip(self):
        """
        :rtype: int
        """
        return self._max_per_chip

    @property
    def max_defaultable(self):
        """
        :rtype: int
        """
        return self._max_defaultable

    @property
    def max_link(self):
        """
        :rtype: int
        """
        return self._max_link

    @property
    def unqiue_routes(self):
        """
        :rtype: int
        """
        return self._unqiue_routes
