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
from pacman.model.graphs.common import Slice
from pacman.model.partitioner_interfaces import AbstractSplitterCommon
from spinn_utilities.overrides import overrides


class SplitterOneToOneLegacy(AbstractSplitterCommon):

    __slots__ = [
        "_machine_vertex",
        "_vertex_slice",
        "_resources_required"]

    SPLITTER_NAME = "1to1SplitterLegacy"

    def __init__(self):
        AbstractSplitterCommon.__init__(self, splitter_name=self.SPLITTER_NAME)
        self._machine_vertex = None
        self._vertex_slice = None
        self._resources_required = None

    def __str__(self):
        return self.STR_MESSAGE.format(self._governed_app_vertex)

    def __repr__(self):
        return self.__str__()

    @overrides(AbstractSplitterCommon.set_governed_app_vertex)
    def set_governed_app_vertex(self, app_vertex):
        AbstractSplitterCommon.set_governed_app_vertex(self, app_vertex)
        self._vertex_slice = Slice(0, self._governed_app_vertex.n_atoms)
        self._resources_required = (
            self._governed_app_vertex.get_resources_used_by_atoms(
                self._vertex_slice))

    @overrides(AbstractSplitterCommon.create_machine_vertices)
    def create_machine_vertices(self, resource_tracker, machine_graph):
        self._machine_vertex = (
            self._governed_app_vertex.create_machine_vertex(
                vertex_slice=self._vertex_slice,
                resources_required=self._resources_required, label=None,
                constraints=None))
        return self._machine_vertex

    @overrides(AbstractSplitterCommon.get_out_going_slices)
    def get_out_going_slices(self):
        return self._vertex_slice, True

    @overrides(AbstractSplitterCommon.get_in_coming_slices)
    def get_in_coming_slices(self):
        return self._vertex_slice, True

    @overrides(AbstractSplitterCommon.get_pre_vertices)
    def get_pre_vertices(self, edge, outgoing_edge_partition):
        if self._machine_vertex is None:
            return []
        return [self._machine_vertex]

    @overrides(AbstractSplitterCommon.get_post_vertices)
    def get_post_vertices(self, edge, outgoing_edge_partition,
                          src_machine_vertex):
        if self._machine_vertex is None:
            return []
        return [self._machine_vertex]

    @overrides(AbstractSplitterCommon.machine_vertices_for_recording)
    def machine_vertices_for_recording(self, variable_to_record):
        if self._machine_vertex is None:
            return []
        return [self._machine_vertex]
