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
from collections import OrderedDict

from six import raise_from, add_metaclass

from pacman.model.graphs.machine import MachineEdge
from pacman.model.partitioner_interfaces.abstract_splitter_common import (
    AbstractSplitterCommon)
from pacman.model.resources import ResourceContainer
from pacman.utilities.algorithm_utilities.\
    partition_algorithm_utilities import get_remaining_constraints
from spinn_utilities.abstract_base import AbstractBase, abstractmethod
from pacman.exceptions import PacmanPartitionException, PacmanValueError
from pacman.model.graphs import AbstractVirtual
from pacman.model.graphs.common import Slice
from spinn_utilities.overrides import overrides


@add_metaclass(AbstractBase)
class AbstractSplitterSlice(AbstractSplitterCommon):
    """ contains default logic for splitting by slice
    """

    __slots__ = ["_called"]

    NOT_SUITABLE_VERTEX_ERROR = (
        "The vertex {} cannot be supported by the {} as"
        " the vertex does not support the required API of "
        "LegacyPartitionerAPI. Please inherit from the class in "
        "pacman.model.partitioner_interfaces.legacy_partitioner_api and try "
        "again.")

    NO_MORE_RESOURCE_AVAILABLE_ERROR = (
        "No more of vertex '{}' would fit on the board:\n"
        "    Allocated so far: {} atoms\n"
        "    Request for SDRAM: {}\n"
        "    Largest SDRAM space: {}")

    FAIL_TO_ALLOCATE_RESOURCES = (
        "Unable to allocate requested resources available to vertex "
        "'{}':\n{}")

    MACHINE_LABEL = "{}:{}:{}"

    def __init__(self, splitter_name):
        AbstractSplitterCommon.__init__(self, splitter_name)
        self._called = False

    def _get_map(self, edge_types):
        """ builds map of machine vertex to edge type

        :param edge_types: the type of edges to add to the dict.

        :return: dict of vertex as key, edge types as list in value
        """
        result = OrderedDict()
        for vertex in self._governed_app_vertex.machine_vertices:
            result[vertex] = edge_types
        return result

    @overrides(AbstractSplitterCommon.get_pre_vertices)
    def get_pre_vertices(self, edge, outgoing_edge_partition):
        return self._get_map([MachineEdge])

    @overrides(AbstractSplitterCommon.get_post_vertices)
    def get_post_vertices(
            self, edge, outgoing_edge_partition, src_machine_vertex):
        return self._get_map([MachineEdge])

    @overrides(AbstractSplitterCommon.get_out_going_slices)
    def get_out_going_slices(self):
        if self._called:
            return self._governed_app_vertex.vertex_slices, True
        else:
            return self._estimate_slices(), False

    @overrides(AbstractSplitterCommon.get_in_coming_slices)
    def get_in_coming_slices(self):
        if self._called:
            return self._governed_app_vertex.vertex_slices, True
        else:
            return self._estimate_slices(), False

    @overrides(AbstractSplitterCommon.machine_vertices_for_recording)
    def machine_vertices_for_recording(self, variable_to_record):
        return list(self._governed_app_vertex.machine_vertices)

    def __split(self, resource_tracker):
        """ breaks a app vertex into its machine vertex bits.

        :param ResourceTracker resource_tracker: res tracker.
        :return: map of slices to resources. for easier usage later.
        """
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
                lo_atom, hi_atom, resource_tracker)

            # Update where we are
            n_atoms_placed = hi_atom + 1

            # Create the vertices
            for used_resources in used_placements:
                slice_resource_map[Slice(lo_atom, hi_atom)] = used_resources
        return slice_resource_map

    def _scale_down_resources(self, lo_atom, hi_atom, resource_tracker):
        """ Reduce the number of atoms on a core so that it fits within the
            resources available.

        :param int lo_atom: the number of atoms already partitioned
        :param int hi_atom: the total number of atoms to place for this vertex
        :param ResourceTracker resource_tracker: Tracker of used resources
        :return: the list of placements made by this method and the new amount
            of atoms partitioned
        :rtype: tuple(iterable(tuple(ApplicationVertex, ResourceContainer)),
            int)
        :raise PacmanPartitionException: when the vertex cannot be partitioned
        """

        used_placements = list()

        # Find the number of atoms that will fit in each vertex given the
        # resources available
        min_hi_atom = hi_atom

        # get resources used by vertex
        vertex_slice = Slice(lo_atom, hi_atom)
        used_resources = self.get_resources_used_by_atoms(vertex_slice)

        x = None
        y = None
        p = None
        ip_tags = None
        reverse_ip_tags = None
        if not isinstance(self._governed_app_vertex, AbstractVirtual):

            # get max resources_available on machine
            resources_available = resource_tracker.\
                get_maximum_constrained_resources_available(
                    used_resources, self._governed_app_vertex.constraints)

            # Work out the ratio of used to available resources
            ratio = self._find_max_ratio(
                used_resources, resources_available,
                resource_tracker.plan_n_time_steps)

            if self._is_fixed_atoms_per_core and ratio > 1.0:
                raise PacmanPartitionException(
                    self.NO_MORE_RESOURCE_AVAILABLE_ERROR.format(
                        self._governed_app_vertex, lo_atom - 1,
                        used_resources.sdram.get_total_sdram(
                            resource_tracker.plan_n_timesteps),
                        resources_available.sdram.get_total_sdram(
                            resource_tracker.plan_n_timesteps)))

            while ratio > 1.0 and hi_atom >= lo_atom:
                # Scale the resources available by the ratio
                old_n_atoms = (hi_atom - lo_atom) + 1
                new_n_atoms = int(old_n_atoms / (ratio * 1.1))

                # Avoid infinite looping
                if old_n_atoms == new_n_atoms:
                    new_n_atoms -= 1

                # Find the new resource usage
                hi_atom = lo_atom + new_n_atoms - 1
                if hi_atom >= lo_atom:
                    vertex_slice = Slice(lo_atom, hi_atom)
                    used_resources = (
                        self.get_resources_used_by_atoms(vertex_slice))
                    ratio = self._find_max_ratio(
                        used_resources, resources_available,
                        resource_tracker.plan_n_time_steps)

            # If we couldn't partition, raise an exception
            if hi_atom < lo_atom:
                raise PacmanPartitionException(
                    self.NO_MORE_RESOURCE_AVAILABLE_ERROR.format(
                        self._governed_app_vertex, lo_atom - 1,
                        used_resources.sdram.get_total_sdram(
                            resource_tracker.plan_n_timesteps),
                        resources_available.sdram.get_total_sdram(
                            resource_tracker.plan_n_timesteps)))

            # Try to scale up until just below the resource usage
            used_resources, hi_atom = self._scale_up_resource_usage(
                used_resources, hi_atom, lo_atom, resources_available, ratio,
                resource_tracker.plan_n_time_steps)

            # If this hi_atom is smaller than the current minimum, update
            # the other placements to use (hopefully) less
            # resources available
            if hi_atom < min_hi_atom:
                min_hi_atom = hi_atom
                used_placements = self._reallocate_resources(
                    used_placements, resource_tracker, lo_atom,
                    hi_atom)

            # Attempt to allocate the resources available for this vertex
            # on the machine
            try:
                (x, y, p, ip_tags, reverse_ip_tags) = \
                    resource_tracker.allocate_constrained_resources(
                        used_resources, self._governed_app_vertex.constraints)
            except PacmanValueError as e:
                raise_from(PacmanValueError(
                    self.FAIL_TO_ALLOCATE_RESOURCES.format(
                        self._governed_app_vertex, e)), e)

        used_placements.append(
            (x, y, p, used_resources, ip_tags, reverse_ip_tags))

        # reduce data to what the parent requires
        final_placements = list()
        for (_, _, _, used_resources, _, _) in used_placements:
            final_placements.append(used_resources)

        return final_placements, min_hi_atom

    def _scale_up_resource_usage(
            self, used_resources, hi_atom, lo_atom, resources, ratio,
            plan_n_time_steps):
        """ Try to push up the number of atoms in a vertex to be as close\
            to the available resources as possible

        :param ResourceContainer used_resources:
            the resources used by the machine so far
        :param int hi_atom: the total number of atoms to place for this vertex
        :param int lo_atom: the number of atoms already partitioned
         :param int plan_n_time_steps: number of time steps to plan for
        :param ResourceContainer resources:
            the resource estimate for the vertex for a given number of atoms
        :param float ratio: the ratio between max atoms and available resources
        :return: the new resources used and the new hi_atom
        :rtype: tuple(ResourceContainer, int)
        """
        previous_used_resources = used_resources
        previous_hi_atom = hi_atom

        # Keep searching while the ratio is still in range,
        # the next hi_atom value is still less than the number of atoms,
        # and the number of atoms is less than the constrained number of atoms
        while ((ratio < 1.0) and (
                hi_atom + 1 < self._governed_app_vertex.n_atoms) and
               (hi_atom - lo_atom + 2 < self._max_atoms_per_core)):

            # Update the hi_atom, keeping track of the last hi_atom which
            # resulted in a ratio < 1.0
            previous_hi_atom = hi_atom
            hi_atom += 1

            # Find the new resource usage, keeping track of the last usage
            # which resulted in a ratio < 1.0
            previous_used_resources = used_resources
            vertex_slice = Slice(lo_atom, hi_atom)
            used_resources = self.get_resources_used_by_atoms(vertex_slice)
            ratio = self._find_max_ratio(
                used_resources, resources, plan_n_time_steps)

        # If we have managed to fit everything exactly (unlikely but possible),
        # return the matched resources and high atom count
        if ratio == 1.0:
            return used_resources, hi_atom

        # At this point, the ratio > 1.0, so pick the last allocation of
        # resources, which will be < 1.0
        return previous_used_resources, previous_hi_atom

    def _reallocate_resources(
            self, used_placements, resource_tracker, lo_atom, hi_atom):
        """ Readjusts resource allocation and updates the placement list to\
            take into account the new layout of the atoms

        :param used_placements:
            the original list of tuples containing placement data
        :type used_placements: list(tuple(
            ApplicationVertex, int, int, int, ResourceContainer,
            list(tuple(int, int)), list(tuple(int, int))))
        :param ResourceTracker resource_tracker: the tracker of resources
        :param int lo_atom: the low atom of a slice to be considered
        :param int hi_atom: the high atom of a slice to be considered
        :return: the new list of tuples containing placement data
        :rtype: list(tuple(
            ApplicationVertex, int, int, int, ResourceContainer,
            list(tuple(int, int)), list(tuple(int, int))))
        """

        new_used_placements = list()
        for (x, y, p, placed_resources, ip_tags, reverse_ip_tags) in \
                used_placements:

            if not isinstance(self._governed_app_vertex, AbstractVirtual):
                # Deallocate the existing resources
                resource_tracker.unallocate_resources(
                    x, y, p, placed_resources, ip_tags, reverse_ip_tags)

            # Get the new resource usage
            vertex_slice = Slice(lo_atom, hi_atom)
            new_resources = self.get_resources_used_by_atoms(vertex_slice)

            if not isinstance(self._governed_app_vertex, AbstractVirtual):
                # Re-allocate the existing resources
                (x, y, p, ip_tags, reverse_ip_tags) = \
                    resource_tracker.allocate_constrained_resources(
                        new_resources, self._governed_app_vertex.constraints)
            new_used_placements.append(
                (x, y, p, new_resources, ip_tags, reverse_ip_tags))
        return new_used_placements

    @staticmethod
    def _ratio(numerator, denominator):
        """ Get the ratio between two values, with special handling for when\
            the denominator is zero.

        :param int numerator:
        :param int denominator:
        :rtype: float
        """
        if denominator == 0:
            return 0.0
        return numerator / denominator

    @classmethod
    def _find_max_ratio(cls, required, available, plan_n_time_steps):
        """ Find the max ratio between the resources.

        :param ResourceContainer required: the resources used by the vertex
        :param ResourceContainer available:
            the max resources available from the machine
        :param int plan_n_time_steps: number of time steps to plan for
        :return: the largest ratio of resources
        :rtype: float
        :raise None: this method does not raise any known exceptions
        """
        cpu_ratio = cls._ratio(
            required.cpu_cycles.get_value(),
            available.cpu_cycles.get_value())
        dtcm_ratio = cls._ratio(
            required.dtcm.get_value(), available.dtcm.get_value())
        sdram_ratio = cls._ratio(
            required.sdram.get_total_sdram(plan_n_time_steps),
            available.sdram.get_total_sdram(plan_n_time_steps))
        return max((cpu_ratio, dtcm_ratio, sdram_ratio))

    @overrides(AbstractSplitterCommon.create_machine_vertices)
    def create_machine_vertices(self, resource_tracker, machine_graph):
        slices_resources_map = self.__split(resource_tracker)
        for vertex_slice in slices_resources_map:
            machine_vertex = self.create_machine_vertex(
                vertex_slice, slices_resources_map[vertex_slice],
                self.MACHINE_LABEL.format(
                    self._governed_app_vertex.label, vertex_slice.lo_atom,
                    vertex_slice.hi_atom),
                get_remaining_constraints(self._governed_app_vertex))
            machine_graph.add_vertex(machine_vertex)
        self._called = True
        return True

    @abstractmethod
    def create_machine_vertex(
            self, vertex_slice, resources, label, remaining_constraints):
        """ creates a machine vertex

        :param vertex_slice: vertex slice
        :param resources: resources
        :param label: human readable label for machine vertex.
        :param remaining_constraints: none partitioner constraints.
        :return: machine vertex
        """

    @abstractmethod
    def get_resources_used_by_atoms(self, vertex_slice):
        """ gets the resources of a slice of atoms from a given app vertex.

        :param vertex_slice: the slice to find the resources of.
        :return: ResourceContainer.
        """

    def _estimate_slices(self):
        """ estimates the slices for when not already been split.

        :return: The estimated slices.
        """
        if self._governed_app_vertex.n_atoms < self._max_atoms_per_core:
            return [Slice(0, self._governed_app_vertex.n_atoms)]
        else:
            slices = list()
            n_atoms_placed = 0
            n_atoms = self._governed_app_vertex.n_atoms
            while n_atoms_placed < n_atoms:
                if n_atoms_placed + self._max_atoms_per_core > n_atoms:
                    slices.append(Slice(
                        n_atoms_placed, n_atoms - n_atoms_placed))
                    n_atoms_placed = n_atoms
                else:
                    slices.append(Slice(
                        n_atoms_placed,
                        n_atoms_placed + self._max_atoms_per_core))
                n_atoms_placed += self._max_atoms_per_core
            return slices
