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
    AbstractDataReader, AbstractContextManager)


class DataRowReader(AbstractDataReader, AbstractContextManager):
    __slots__ = [
        "_index",
        "_data",
    ]

    def __init__(self, data):
        self._index = 0
        self._data = data

    @overrides(AbstractDataReader.read)
    def read(self, n_bytes=None):
        previous = self._index
        if n_bytes is None:
            self._index = len(self._data)
        else:
            self._index += n_bytes
        return self._data[previous:self._index]

    @overrides(AbstractDataReader.tell)
    def tell(self):
        return self._index

    @overrides(AbstractContextManager.close, extend_doc=False)
    def close(self):
        """ Does Nothing """

    def __eq__(self, other):
        """ Equality mainly for testing.
        """
        # pylint: disable=protected-access
        if not isinstance(other, DataRowReader):
            return False
        return self._data == other._data

    def __ne__(self, other):
        if not isinstance(other, DataRowReader):
            return True
        return not self.__eq__(other)
