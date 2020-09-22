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
from spinn_front_end_common.interface.partitioner_splitters.\
    abstract_splitters.abstract_splitter_slice import AbstractSplitterSlice
from spinn_utilities.overrides import overrides


class SplitterPerEthernetChipLegacy(AbstractSplitterSlice):

    SPLITTER_NAME = "SplitterPerEthernetChipLegacy"

    def __init__(self):
        AbstractSplitterSlice.__init__(self, self.SPLITTER_NAME)

    @overrides(AbstractSplitterSlice.create_machine_vertices)
    def create_machine_vertices(self, resource_tracker, machine_graph):
        return []
