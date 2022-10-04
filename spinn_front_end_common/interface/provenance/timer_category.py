# Copyright (c) 2022 The University of Manchester
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

from enum import auto, Enum


class TimerCategory(Enum):
    """
    Different Categories a FecTimer can be in

    """
    # Category Constants
    WAITING = (auto(), "Waiting")
    SETTING_UP = (auto(), "In Setup")
    RUN_OTHER = (auto(), "In run other")
    GET_MACHINE = (auto(), "Turning on Machine")
    LOADING = (auto(), "Loading Stage")
    DATA_GENERATION = (auto(), "data_generation")
    MAPPING = (auto(), "Mapping Stage")
    RUN_LOOP = (auto(), "Running Stage")
    RESETTING = (auto(), "Resetting")
    SHUTTING_DOWN = (auto(), "Shutting down")

    def __new__(cls, value, category_name):
        # pylint: disable=protected-access
        obj = object.__new__(cls)
        obj._value_ = value
        obj._category_name = category_name
        return obj

    @property
    def category_name(self):
        return self._category_name
