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

from spinn_utilities.overrides import overrides
from spinn_storage_handlers.abstract_classes import (
    AbstractDataWriter, AbstractContextManager)


class DataRowWriter(AbstractDataWriter, AbstractContextManager):
    __slots__ = [
        "_x",
        "_y",
        "_p",
        "_targets",
        "_data",
        "_closed"
    ]

    def __init__(self, x, y, p, targets):
        self._x = x
        self._y = y
        self._p = p
        self._targets = targets
        self._data = bytearray()
        self._closed = False

    @overrides(AbstractDataWriter.write)
    def write(self, data):
        assert self._closed is False
        self._data += data

    @overrides(AbstractContextManager.close, extend_doc=False)
    def close(self):
        """ Closes the writer if not already closed.
        """
        if not self._closed:
            self._targets.write_data_spec(
                self._x, self._y, self._p, self._data)
            self._closed = True
