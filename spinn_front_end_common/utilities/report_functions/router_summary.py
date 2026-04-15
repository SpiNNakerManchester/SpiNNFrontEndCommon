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


class RouterSummary(object):
    """
    Summary of information about a router.
    """

    __slots__ = (
        "_total_entries",
        "_max_per_chip",
        "_max_defaultable",
        "_max_link",
        "_unqiue_routes")

    def __init__(self, total_entries: int, max_per_chip: int,
                 max_defaultable: int, max_link: int, unqiue_routes: int):
        """
        :param total_entries: Total entries in all routes
        :param max_per_chip: Largest number of routes on any Chip
        :param max_defaultable:
            Largest number of defaultable routes on any Chip
        :param max_link:
            Largest number of link only routes on any Chip
        :param unqiue_routes:
            Largest number of unique spinnaker routes on any Chip
        """
        self._total_entries = total_entries
        self._max_per_chip = max_per_chip
        self._max_defaultable = max_defaultable
        self._max_link = max_link
        self._unqiue_routes = unqiue_routes

    @property
    def total_entries(self) -> int:
        """
        The total entries as passed into the init
        """
        return self._total_entries

    @property
    def max_per_chip(self) -> int:
        """
        The maximum number of routes per Chip
        """
        return self._max_per_chip

    @property
    def max_defaultable(self) -> int:
        """
        The maximum number of defaultable routes per Chip
        """
        return self._max_defaultable

    @property
    def max_link(self) -> int:
        """
        The maximum number of links
        """
        return self._max_link

    @property
    def unqiue_routes(self) -> int:
        """
        The number of unique routes
        """
        return self._unqiue_routes
