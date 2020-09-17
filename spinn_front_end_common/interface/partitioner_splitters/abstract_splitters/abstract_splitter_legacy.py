# Copyright (c) 2020-2021 The University of Manchester
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
from six import add_metaclass

from pacman.exceptions import PacmanConfigurationException
from pacman.model.partitioner_interfaces.abstract_splitter_common import (
    AbstractSplitterCommon)
from pacman.model.partitioner_interfaces.legacy_partitioner_api import (
    LegacyPartitionerAPI)
from spinn_front_end_common.interface.partitioner_splitters.\
    abstract_splitters.abstract_splitter_slice import AbstractSplitterSlice
from spinn_utilities.abstract_base import AbstractBase
from spinn_utilities.overrides import overrides


@add_metaclass(AbstractBase)
class AbstractSplitterLegacy(AbstractSplitterSlice):
    """ contains the checks for legacy api and the printing of error messages

    """

    __slots__ = []

    NOT_SUITABLE_VERTEX_ERROR = (
        "The vertex {} cannot be supported by the {} as"
        " the vertex does not support the required API of "
        "LegacyPartitionerAPI. Please inherit from the class in "
        "pacman.model.partitioner_interfaces.legacy_partitioner_api and try "
        "again.")

    SPLITTER_NAME = "SplitterLegacy"

    def __init__(self, splitter_name=None):
        if splitter_name is None:
            splitter_name = self.SPLITTER_NAME
        AbstractSplitterSlice.__init__(self, splitter_name)

    @overrides(AbstractSplitterSlice.set_governed_app_vertex)
    def set_governed_app_vertex(self, app_vertex):
        AbstractSplitterCommon.set_governed_app_vertex(self, app_vertex)
        if not isinstance(app_vertex, LegacyPartitionerAPI):
            raise PacmanConfigurationException(
                self.NOT_SUITABLE_VERTEX_ERROR.format(
                    self.__splitter_name, app_vertex.label))
