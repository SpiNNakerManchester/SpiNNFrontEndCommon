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
from pacman.model.partitioner_interfaces import LegacyPartitionerAPI
from pacman.model.graphs.application import ApplicationVertex
from .chip_power_monitor_machine_vertex import ChipPowerMonitorMachineVertex


class ChipPowerMonitor(ApplicationVertex, LegacyPartitionerAPI):
    """ Represents idle time recording code in a application graph.
    """
    __slots__ = ["_sampling_frequency"]

    def __init__(
            self, label, sampling_frequency, constraints=None):
        """
        :param str label: vertex label
        :param constraints: constraints for the vertex
        :type constraints:
            iterable(~pacman.model.constraints.AbstractConstraint)
        :param int sampling_frequency: how many microseconds between sampling
        """
        super().__init__(label, constraints, 1)
        self._sampling_frequency = sampling_frequency

    @property
    @overrides(LegacyPartitionerAPI.n_atoms)
    def n_atoms(self):
        return 1

    @overrides(LegacyPartitionerAPI.create_machine_vertex)
    def create_machine_vertex(
            self,
            vertex_slice, resources_required,  # @UnusedVariable
            label=None, constraints=None):
        machine_vertex = ChipPowerMonitorMachineVertex(
            constraints=constraints, label=label,
            sampling_frequency=self._sampling_frequency,  app_vertex=self)
        if vertex_slice:
            assert (vertex_slice == machine_vertex.vertex_slice)
        if resources_required:
            assert (resources_required ==
                    machine_vertex.resources_required)
        return machine_vertex

    @overrides(LegacyPartitionerAPI.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(
            self, vertex_slice,  # @UnusedVariable
            ):
        # pylint: disable=arguments-differ
        return ChipPowerMonitorMachineVertex.get_resources(
            self._sampling_frequency)
