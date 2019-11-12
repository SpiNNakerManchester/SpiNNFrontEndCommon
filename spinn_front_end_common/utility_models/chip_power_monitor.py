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
from pacman.executor.injection_decorator import inject_items
from pacman.model.graphs.application import ApplicationVertex
from spinn_front_end_common.abstract_models import (
    AbstractGeneratesDataSpecification, AbstractHasAssociatedBinary)
from .chip_power_monitor_machine_vertex import ChipPowerMonitorMachineVertex


class ChipPowerMonitor(
        ApplicationVertex, AbstractHasAssociatedBinary,
        AbstractGeneratesDataSpecification):
    """ Represents idle time recording code in a application graph.
    """
    __slots__ = ["_n_samples_per_recording", "_sampling_frequency"]

    def __init__(
            self, label, constraints, n_samples_per_recording,
            sampling_frequency):
        """
        :param label: vertex label
        :type label: str
        :param constraints: constraints for the vertex
        :type constraints: \
            iterable(~pacman.model.constraints.AbstractConstraint)
        :param n_samples_per_recording: \
            how many samples to take before recording to SDRAM the total
        :type n_samples_per_recording: int
        :param sampling_frequency: how many microseconds between sampling
        :type sampling_frequency: int
        """
        super(ChipPowerMonitor, self).__init__(label, constraints, 1)
        self._n_samples_per_recording = n_samples_per_recording
        self._sampling_frequency = sampling_frequency

    @property
    @overrides(ApplicationVertex.n_atoms)
    def n_atoms(self):
        return 1

    @overrides(ApplicationVertex.create_machine_vertex)
    def create_machine_vertex(
            self,
            vertex_slice, resources_required,  # @UnusedVariable
            label=None, constraints=None):
        return ChipPowerMonitorMachineVertex(
            constraints=constraints, label=label,
            n_samples_per_recording=self._n_samples_per_recording,
            sampling_frequency=self._sampling_frequency)

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return ChipPowerMonitorMachineVertex.binary_file_name()

    @inject_items({"time_scale_factor": "TimeScaleFactor",
                   "machine_time_step": "MachineTimeStep",
                   "n_machine_time_steps": "PlanNTimeSteps"})
    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification,
        additional_arguments={
            "machine_time_step", "time_scale_factor", "n_machine_time_steps"})
    def generate_data_specification(
            self, spec, placement, machine_time_step, time_scale_factor,
            n_machine_time_steps):
        # pylint: disable=too-many-arguments, arguments-differ
        # pylint: disable=protected-access

        # generate spec for the machine vertex
        placement.vertex._generate_data_specification(
            spec, machine_time_step, time_scale_factor, n_machine_time_steps)

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ChipPowerMonitorMachineVertex.binary_start_type()

    @inject_items({
        "machine_time_step": "MachineTimeStep",
        "time_scale_factor": "TimeScaleFactor"})
    @overrides(ApplicationVertex.get_resources_used_by_atoms,
               additional_arguments={"machine_time_step", "time_scale_factor"})
    def get_resources_used_by_atoms(
            self, vertex_slice,  # @UnusedVariable
            machine_time_step, time_scale_factor):
        # pylint: disable=arguments-differ
        return ChipPowerMonitorMachineVertex.get_resources(
            machine_time_step, time_scale_factor,
            self._n_samples_per_recording, self._sampling_frequency)
