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
from six import raise_from
from pacman.exceptions import PacmanPartitionException, PacmanValueError
from pacman.model.graphs import AbstractVirtual
from pacman.model.graphs.common import Slice
from spinn_front_end_common.interface.partitioner_splitters.abstract_splitters import \
    AbstractSplitterSlice
from spinn_front_end_common.interface.partitioner_splitters.\
    abstract_splitters.abstract_splitter_legacy import AbstractSplitterLegacy
from spinn_utilities.overrides import overrides


class SplitterSliceLegacy(AbstractSplitterLegacy, AbstractSplitterSlice):

    __slots__ = [
        "__splitter_name"
    ]

    def __init__(self, splitter_name=None):
        if splitter_name is None:
            splitter_name = self.SPLITTER_NAME
        AbstractSplitterLegacy.__init__(self, splitter_name)
        AbstractSplitterSlice.__init__(self, splitter_name)

    @overrides(AbstractSplitterLegacy.create_machine_vertex)
    def create_machine_vertex(
            self, vertex_slice, resources, label, remaining_constraints):
        return self._governed_app_vertex.create_machine_vertex(
            vertex_slice, resources, label, remaining_constraints)
