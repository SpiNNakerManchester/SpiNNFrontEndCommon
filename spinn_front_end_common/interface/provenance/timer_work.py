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


class TimerWork(Enum):
    """
    Different Work types an Algorithm could be doing
    """

    OTHER = (auto(), "Other")
    GET_MACHINE = (auto(), "Turning on Machine")
    LOADING = (auto(), "Loading Stage")
    # LOADING
    BITFIELD = (auto(), "BitField work")
    # Only for on Machine Compression
    COMPRESSING = (auto(), "Compressing")
    CONTROL = (auto(), "Control")
    SYNAPSE = (auto(), "Expanding Synapse")
    RUNNING = (auto(), "Running")
    EXTRACTING = (auto(), "Extracting")
    # TODO is in right to treat this separately
    EXTRACT_DATA = (auto(), "Extracting Data")
    REPORT = (auto(), "Reporting")

    def __new__(cls, value, work_name):
        # pylint: disable=protected-access
        obj = object.__new__(cls)
        obj._value_ = value
        obj._work_name = work_name
        return obj

    @property
    def work_name(self):
        return self._work_name
