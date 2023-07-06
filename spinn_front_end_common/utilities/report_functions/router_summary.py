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
        self._total_entries = total_entries
        self._max_per_chip = max_per_chip
        self._max_defaultable = max_defaultable
        self._max_link = max_link
        self._unqiue_routes = unqiue_routes

    @property
    def total_entries(self) -> int:
        """
        :rtype: int
        """
        return self._total_entries

    @property
    def max_per_chip(self) -> int:
        """
        :rtype: int
        """
        return self._max_per_chip

    @property
    def max_defaultable(self) -> int:
        """
        :rtype: int
        """
        return self._max_defaultable

    @property
    def max_link(self) -> int:
        """
        :rtype: int
        """
        return self._max_link

    @property
    def unqiue_routes(self) -> int:
        """
        :rtype: int
        """
        return self._unqiue_routes
