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
from pacman.model.partitioner_interfaces import AbstractSplitterCommon
from spinn_utilities.overrides import overrides


class SplitterPerEthernetChipLegacy(AbstractSplitterCommon):

    SPLITTER_NAME = "SplitterPerEthernetChipLegacy"

    def __init__(self):
        AbstractSplitterCommon.__init__(self, self.SPLITTER_NAME)

    @overrides(AbstractSplitterCommon.create_machine_vertices)
    def create_machine_vertices(self, resource_tracker, machine_graph):
        return []

    @overrides(AbstractSplitterCommon.get_out_going_slices)
    def get_out_going_slices(self):
        return []

    @overrides(AbstractSplitterCommon.get_in_coming_slices)
    def get_in_coming_slices(self):
        return []

    @overrides(AbstractSplitterCommon.get_pre_vertices)
    def get_pre_vertices(self, edge, outgoing_edge_partition):
        return self._governed_app_vertex.machine_vertices

    @overrides(AbstractSplitterCommon.get_post_vertices)
    def get_post_vertices(self, edge, outgoing_edge_partition,
                          src_machine_vertex):
        return self._governed_app_vertex.machine_vertices

    @overrides(AbstractSplitterCommon.machine_vertices_for_recording)
    def machine_vertices_for_recording(self, variable_to_record):
        return self._governed_app_vertex.machine_vertices
