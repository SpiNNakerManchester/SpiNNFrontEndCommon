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
from spinn_front_end_common.interface.partitioner_splitters.\
    abstract_splitters.abstract_splitter_legacy import AbstractSplitterLegacy
from spinn_utilities.overrides import overrides


class SplitterSliceLegacy(AbstractSplitterLegacy):

    __slots__ = [
        "__splitter_name"
    ]

    NOT_SUITABLE_VERTEX_ERROR = (
        "The vertex {} cannot be supported by the {} as"
        " the vertex does not support the required API of "
        "LegacyPartitionerAPI. Please inherit from the class in "
        "pacman.model.partitioner_interfaces.legacy_partitioner_api and try "
        "again.")

    SPLITTER_NAME = "SplitterSliceLegacy"

    def __init__(self, splitter_name=None):
        if splitter_name is None:
            splitter_name = self.SPLITTER_NAME
        AbstractSplitterLegacy.__init__(self, splitter_name)

    def __split(self, resource_tracker, machine_graph):
        """ TODO NEEDS FILLING IN. STEAL FROM PARTITION AND PLACE"""

    @overrides(AbstractSplitterLegacy.create_machine_vertices)
    def create_machine_vertices(self, resource_tracker, machine_graph):
        slices_resources_map = self.__split(resource_tracker, machine_graph)
        for vertex_slice in slices_resources_map:
            machine_vertex = self._governed_app_vertex.create_machine_vertex(
                vertex_slice, slices_resources_map[vertex_slice])
            machine_graph.add_vertex(machine_vertex)
        return True
