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
from pacman.model.graphs.common import Slice
from pacman.utilities.algorithm_utilities.partition_algorithm_utilities import \
    get_remaining_constraints
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

    def __split(self, resource_tracker):
        slice_resource_map = dict()
        n_atoms_placed = 0
        n_atoms = self._governed_app_vertex.n_atoms
        while n_atoms_placed < n_atoms:
            lo_atom = n_atoms_placed
            hi_atom = lo_atom + self._max_atoms_per_core - 1
            if hi_atom >= n_atoms:
                hi_atom = n_atoms - 1

            # Scale down the number of atoms to fit the available resources
            used_placements, hi_atom = self._scale_down_resources(
                lo_atom, hi_atom, vertices, resource_tracker,
                fixed_n_atoms)

            # Update where we are
            n_atoms_placed = hi_atom + 1

            # Create the vertices
            for (_, used_resources) in used_placements:
                slice_resource_map[Slice(lo_atom, hi_atom)] = used_resources

        """ TODO NEEDS FILLING IN. STEAL FROM PARTITION AND PLACE"""

    @overrides(AbstractSplitterLegacy.create_machine_vertices)
    def create_machine_vertices(self, resource_tracker, machine_graph):
        slices_resources_map = self.__split(resource_tracker, machine_graph)
        for vertex_slice in slices_resources_map:
            machine_vertex = self._governed_app_vertex.create_machine_vertex(
                vertex_slice, slices_resources_map[vertex_slice])
            machine_graph.add_vertex(machine_vertex)
        return True
