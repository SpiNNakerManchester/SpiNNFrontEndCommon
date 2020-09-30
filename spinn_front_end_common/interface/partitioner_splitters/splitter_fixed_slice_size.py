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
import sys

from pacman.exceptions import PacmanPartitionException
from pacman.model.constraints.partitioner_constraints import (
    FixedVertexAtomsConstraint, MaxVertexAtomsConstraint)
from pacman.model.graphs.common import Slice
from pacman.model.partitioner_interfaces import AbstractSplitterCommon
from pacman.utilities import utility_calls
from spinn_utilities.overrides import overrides
from pacman.utilities.algorithm_utilities.partition_algorithm_utilities \
    import get_remaining_constraints


class SplitterFixedSliceSized(AbstractSplitterCommon):
    """ Splitter that operates off the max atoms per core constraint and
    fixed atoms per core constraints. Will ensure its feasible to partition at
    that atoms per core.
    """

    __slots__ = [
        # bool flag for if its been called already.
        "__been_called",

        # atom constraint
        "__max_atom_by_constraint",

        # bool if hard or soft.
        "__fixed_atom_by_constraint"]

    SPLITTER_NAME = "FixedSizeSplitter"

    CONFLICT_CONSTRAINTS_ERROR_MESSAGE = (
        "Max size of {} is incompatible with fixed size of {}")

    CONFLICT_MULTIPLE_FIXED_ATOM_CONSTRAINTS = (
        "Vertex has multiple contradictory fixed atom constraints"
        " - cannot be both {} and {}")

    NOT_ENOUGH_RESOURCES_ERROR_MESSAGE = (
        "Not enough resources available to create vertex")

    def __init__(self):
        AbstractSplitterCommon.__init__(self, self.SPLITTER_NAME)
        self.__been_called = False
        self.__max_atom_by_constraint = None
        self.__fixed_atom_by_constraint = None

    @overrides(AbstractSplitterCommon.set_governed_app_vertex)
    def set_governed_app_vertex(self, app_vertex):
        AbstractSplitterCommon.set_governed_app_vertex(self, app_vertex)
        self.__max_atom_by_constraint, self.__fixed_atom_by_constraint = (
            self._compute_constraint_max_atoms())
        if (self.__fixed_atom_by_constraint is not None and
                self.__max_atom_by_constraint <
                self.__fixed_atom_by_constraint):
            raise PacmanPartitionException(
                self.CONFLICT_CONSTRAINTS_ERROR_MESSAGE.format(
                    self.__max_atom_by_constraint,
                    self.__fixed_atom_by_constraint))

    @overrides(AbstractSplitterCommon.create_machine_vertices)
    def create_machine_vertices(self, resource_tracker, machine_graph):
        atoms_per_core = self._compute_atoms_per_core(resource_tracker)
        if atoms_per_core < 1.0:
            raise PacmanPartitionException(
                self._NOT_ENOUGH_RESOURCES_ERROR_MESSAGE)
        self.__split(atoms_per_core, machine_graph, resource_tracker)
        self.__been_called = True
        return True

    @overrides(AbstractSplitterCommon.get_out_going_slices)
    def get_out_going_slices(self):
        if self.__been_called:
            return self._governed_app_vertex.vertex_slices, True
        else:
            self._get_slices_estimate(), False

    @overrides(AbstractSplitterCommon.get_in_coming_slices)
    def get_in_coming_slices(self):
        if self.__been_called:
            return self._governed_app_vertex.vertex_slices, True
        else:
            return self._get_slices_estimate(), False

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

    def _get_slices_estimate(self):
        """ generates estimate of slices

        :return: list of slices
        """
        slices = list()
        atoms = (
            int(self.__fixed_atom_by_constraint) if
            self.__fixed_atom_by_constraint is not None else
            int(self.__max_atom_by_constraint))

        for first in range(0, self._governed_app_vertex.n_atoms, atoms):
            # Determine vertex size
            last = int(min(
                first + atoms, self._governed_app_vertex.n_atoms) - 1)
            slices.append(Slice(first, last))
        return slices

    def __split(self, atoms_per_core, machine_graph, resource_tracker):
        """ executes the splitting of the app vertex into machine vertices by
            atoms per core.

        :param int atoms_per_core: how many atoms to split per machine vertex
        :param MachineGraph machine_graph: machine graph
        :param ResourceTracker resource_tracker: resource tracker
        :return:
        """
        # Partition into vertices
        for first in range(
                0, self._governed_app_vertex.n_atoms, atoms_per_core):

            # Determine vertex size
            last = int(min(
                first + atoms_per_core, self._governed_app_vertex.n_atoms) - 1)
            if first < 0 or last < 0:
                raise PacmanPartitionException(
                    self.NOT_ENOUGH_RESOURCES_ERROR_MESSAGE)

            # Create and store new vertex, and increment elements first
            vertex_slice = Slice(first, last)
            resources = self._governed_app_vertex.get_resources_used_by_atoms(
                vertex_slice)

            m_vertex = self._governed_app_vertex.create_machine_vertex(
                vertex_slice, resources,
                "{}:{}:{}".format(
                    self._governed_app_vertex.label, first, last),
                get_remaining_constraints(self._governed_app_vertex))
            machine_graph.add_vertex(m_vertex)

            # update allocated resources
            resource_tracker.allocate_constrained_resources(
                resources, self._governed_app_vertex.constraints)

    def _compute_constraint_max_atoms(self):
        """ searches the constraints looking for fixed and max atom
        constraints. Will report if conflicts are in the sets.

        :return: (fixed_atoms, max_atoms)
        """
        fixed_atoms = None
        for fa_constraint in utility_calls.locate_constraints_of_type(
                self._governed_app_vertex.constraints,
                FixedVertexAtomsConstraint):
            if fixed_atoms is not None and fixed_atoms != fa_constraint.size:
                raise PacmanPartitionException(
                    self.CONFLICT_MULTIPLE_FIXED_ATOM_CONSTRAINTS.format(
                        fixed_atoms, fa_constraint.size))
            fixed_atoms = fa_constraint.size

        max_atom_values = list()
        for max_atom_constraint in utility_calls.locate_constraints_of_type(
                self._governed_app_vertex.constraints,
                MaxVertexAtomsConstraint):
            max_atom_values.append(float(max_atom_constraint.size))
        if len(max_atom_values) != 0:
            max_atoms = min(max_atom_values)
        else:
            max_atoms = sys.maxsize

        return fixed_atoms, max_atoms

    def _compute_atoms_per_core(self, resource_tracker):
        """ Work out how many atoms per core are required for the given\
            vertex. Assumes that the first atom of the vertex is fully\
            representative.
        :param ResourceTracker resource_tracker: resource tracker
        :rtype: int
        :raise PacmanPartitionException:
            If something goes wrong with the partitioning
        """
        # Get the usage of the first atom, then assume that this will be the
        # usage of all the atoms.
        requirements = self._governed_app_vertex.get_resources_used_by_atoms(
            Slice(0, 1))

        # Locate the maximum resources available
        limits = resource_tracker.get_maximum_constrained_resources_available(
            requirements, self._governed_app_vertex.constraints)

        # Find the ratio of each of the resources - if 0 is required,
        # assume the ratio is the max available
        atoms_per_sdram = self._get_ratio(
            limits.sdram.get_total_sdram(resource_tracker.plan_n_time_steps),
            requirements.sdram.get_total_sdram(
                resource_tracker.plan_n_time_steps))
        atoms_per_dtcm = self._get_ratio(
            limits.dtcm.get_value(), requirements.dtcm.get_value())
        atoms_per_cpu = self._get_ratio(
            limits.cpu_cycles.get_value(), requirements.cpu_cycles.get_value())

        max_atom_values = [
            atoms_per_sdram, atoms_per_dtcm, atoms_per_cpu,
            self.__max_atom_by_constraint]
        max_atoms = min(max_atom_values)

        return (int(self.__fixed_atom_by_constraint) if
                self.__fixed_atom_by_constraint is not None else
                int(max_atoms))
