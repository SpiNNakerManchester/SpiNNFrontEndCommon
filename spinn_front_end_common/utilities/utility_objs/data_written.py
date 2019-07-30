# Copyright (c) 2017-2019 The University of Manchester
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


class DataWritten(object):
    """ Describes data written to SpiNNaker.
    """

    __slots__ = [
        "_memory_used", "_memory_written", "_start_address"]

    def __init__(self, start_address, memory_used, memory_written):
        self._start_address = start_address
        self._memory_used = memory_used
        self._memory_written = memory_written

    @property
    def memory_used(self):
        return self._memory_used

    @property
    def start_address(self):
        return self._start_address

    @property
    def memory_written(self):
        return self._memory_written

    def __eq__(self, other):
        if not isinstance(other, DataWritten):
            return False
        return (self._start_address == other.start_address and
                self._memory_used == other.memory_used and
                self._memory_written == other.memory_written)
