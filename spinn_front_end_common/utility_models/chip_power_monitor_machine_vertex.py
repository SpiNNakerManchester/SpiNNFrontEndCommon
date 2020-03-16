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

import math
import logging
from enum import Enum
import numpy
from data_specification.enums import DataType
from pacman.executor.injection_decorator import (
    inject_items, supports_injection)
from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import (
    CPUCyclesPerTickResource, DTCMResource, ResourceContainer, VariableSDRAM)
from spinn_front_end_common.abstract_models import (
    AbstractGeneratesDataSpecification, AbstractHasAssociatedBinary)
from spinn_front_end_common.interface.buffer_management import (
    recording_utilities)
from spinn_front_end_common.interface.buffer_management.buffer_models import (
    AbstractReceiveBuffersToHost)
from spinn_front_end_common.utilities import globals_variables
from spinn_front_end_common.utilities.constants import (
    SYSTEM_BYTES_REQUIREMENT, SIMULATION_N_BYTES, BYTES_PER_WORD)
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spinn_front_end_common.utilities.helpful_functions import (
    locate_memory_region_for_placement)
from spinn_front_end_common.interface.simulation.simulation_utilities import (
    get_simulation_header_array)

logger = FormatAdapter(logging.getLogger(__name__))
BINARY_FILE_NAME = "chip_power_monitor.aplx"

RECORDING_SIZE_PER_ENTRY = 18 * BYTES_PER_WORD
DEFAULT_MALLOCS_USED = 3
CONFIG_SIZE_IN_BYTES = 2 * BYTES_PER_WORD


@supports_injection
class ChipPowerMonitorMachineVertex(
        MachineVertex, AbstractHasAssociatedBinary,
        AbstractGeneratesDataSpecification, AbstractReceiveBuffersToHost):
    """ Machine vertex for C code representing functionality to record\
        idle times in a machine graph.

    :param label: vertex label
    :type label: str
    :param constraints: constraints on this vertex
    :type constraints: \
        iterable(~pacman.model.constraints.AbstractConstraint)
    :param n_samples_per_recording: how may samples between recording entry
    :type n_samples_per_recording: int
    :param sampling_frequency: how often to sample, in microseconds
    :type sampling_frequency: int
    """
    __slots__ = ["_n_samples_per_recording", "_sampling_frequency"]

    class _REGIONS(Enum):
        # data regions
        SYSTEM = 0
        CONFIG = 1
        RECORDING = 2

    #: which channel in the recording region has the recorded samples
    _SAMPLE_RECORDING_CHANNEL = 0

    def __init__(
            self, label, constraints, n_samples_per_recording,
            sampling_frequency):
        super(ChipPowerMonitorMachineVertex, self).__init__(
            label=label, constraints=constraints)
        self._n_samples_per_recording = n_samples_per_recording
        self._sampling_frequency = sampling_frequency

    @property
    def sampling_frequency(self):
        return self._sampling_frequency

    @property
    def n_samples_per_recording(self):
        return self._n_samples_per_recording

    @property
    @overrides(MachineVertex.resources_required)
    def resources_required(self):
        # pylint: disable=arguments-differ
        sim = globals_variables.get_simulator()
        return self.get_resources(
            sim.machine_time_step, sim.time_scale_factor,
            self._n_samples_per_recording, self._sampling_frequency)

    @staticmethod
    def get_resources(
            time_step, time_scale_factor,
            n_samples_per_recording, sampling_frequency):
        """ Get the resources used by this vertex

        :rtype: ~pacman.model.resources.ResourceContainer
        """
        # pylint: disable=too-many-locals
        step_in_microseconds = (time_step * time_scale_factor)
        # The number of sample per step CB believes does not have to be an int
        samples_per_step = (step_in_microseconds / sampling_frequency)
        recording_per_step = (samples_per_step / n_samples_per_recording)
        max_recording_per_step = math.ceil(recording_per_step)
        overflow_recordings = max_recording_per_step - recording_per_step
        system = SYSTEM_BYTES_REQUIREMENT
        config = CONFIG_SIZE_IN_BYTES
        recording = recording_utilities.get_recording_header_size(1)
        recording += recording_utilities.get_recording_data_constant_size(1)
        fixed_sdram = system + config + recording
        with_overflow = (
            fixed_sdram + overflow_recordings * RECORDING_SIZE_PER_ENTRY)
        per_timestep = recording_per_step * RECORDING_SIZE_PER_ENTRY

        container = ResourceContainer(
            sdram=VariableSDRAM(with_overflow, per_timestep),
            cpu_cycles=CPUCyclesPerTickResource(100),
            dtcm=DTCMResource(100))
        return container

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return BINARY_FILE_NAME

    @staticmethod
    def binary_file_name():
        """ Return the string binary file name

        :rtype: str
        """
        return BINARY_FILE_NAME

    @inject_items({"time_scale_factor": "TimeScaleFactor",
                   "machine_time_step": "MachineTimeStep",
                   "data_n_time_steps": "DataNTimeSteps"})
    @overrides(AbstractGeneratesDataSpecification.generate_data_specification,
               additional_arguments={
                   "machine_time_step", "time_scale_factor",
                   "data_n_time_steps"})
    def generate_data_specification(
            self, spec, placement,  # @UnusedVariable
            machine_time_step, time_scale_factor, data_n_time_steps):
        # pylint: disable=too-many-arguments, arguments-differ
        self._generate_data_specification(
            spec, machine_time_step, time_scale_factor, data_n_time_steps)

    def _generate_data_specification(
            self, spec, machine_time_step, time_scale_factor,
            data_n_time_steps):
        """ Supports the application vertex calling this directly

        :param spec: data spec
        :param machine_time_step: machine time step
        :param time_scale_factor: time scale factor
        :param data_n_time_steps: timesteps to reserve data for
        :rtype: None
        """
        # pylint: disable=too-many-arguments
        spec.comment("\n*** Spec for ChipPowerMonitor Instance ***\n\n")

        # Construct the data images needed for the Neuron:
        self._reserve_memory_regions(spec)
        self._write_setup_info(
            spec, machine_time_step, time_scale_factor, data_n_time_steps)
        self._write_configuration_region(spec)

        # End-of-Spec:
        spec.end_specification()

    def _write_configuration_region(self, spec):
        """ Write the data needed by the C code to configure itself

        :param spec: spec object
        :rtype: None
        """
        spec.switch_write_focus(region=self._REGIONS.CONFIG.value)
        spec.write_value(self._n_samples_per_recording,
                         data_type=DataType.UINT32)
        spec.write_value(self._sampling_frequency, data_type=DataType.UINT32)

    def _write_setup_info(
            self, spec, machine_time_step, time_scale_factor,
            n_machine_time_steps):
        """ Writes the system data as required.

        :param spec: the DSG spec writer
        :param machine_time_step: the machine time step
        :param time_scale_factor: the time scale factor
        :rtype: None
        """
        # pylint: disable=too-many-arguments
        spec.switch_write_focus(region=self._REGIONS.SYSTEM.value)
        spec.write_array(get_simulation_header_array(
            self.get_binary_file_name(), machine_time_step, time_scale_factor))

        spec.switch_write_focus(region=self._REGIONS.RECORDING.value)
        recorded_region_sizes = [
            self._deduce_sdram_requirements_per_timer_tick(
                machine_time_step, time_scale_factor) * n_machine_time_steps]
        spec.write_array(recording_utilities.get_recording_header_array(
            recorded_region_sizes))

    def _reserve_memory_regions(self, spec):
        """ Reserve the DSG memory regions as required

        :param spec: the DSG specification to reserve in
        :rtype: None
        """
        spec.comment("\nReserving memory space for data regions:\n\n")

        # Reserve memory:
        spec.reserve_memory_region(
            region=self._REGIONS.SYSTEM.value,
            size=SIMULATION_N_BYTES,
            label='system')
        spec.reserve_memory_region(
            region=self._REGIONS.CONFIG.value,
            size=CONFIG_SIZE_IN_BYTES, label='config')
        spec.reserve_memory_region(
            region=self._REGIONS.RECORDING.value,
            size=recording_utilities.get_recording_header_size(1),
            label="Recording")

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return self.binary_start_type()

    @staticmethod
    def binary_start_type():
        """ The type of binary that implements this vertex

        :return: starttype enum
        :rtype: ExecutableType
        """
        return ExecutableType.USES_SIMULATION_INTERFACE

    @overrides(AbstractReceiveBuffersToHost.get_recording_region_base_address)
    def get_recording_region_base_address(self, txrx, placement):
        return locate_memory_region_for_placement(
            placement, self._REGIONS.RECORDING.value, txrx)

    @overrides(AbstractReceiveBuffersToHost.get_recorded_region_ids)
    def get_recorded_region_ids(self):
        return [0]

    def _deduce_sdram_requirements_per_timer_tick(
            self, machine_time_step, time_scale_factor):
        """ Deduce SDRAM usage per timer tick

        :param machine_time_step: the machine time step
        :param time_scale_factor: the time scale factor
        :return: the SDRAM usage
        """
        timer_tick_in_micro_seconds = machine_time_step * time_scale_factor
        recording_time = \
            self._sampling_frequency * self._n_samples_per_recording
        n_entries = math.floor(timer_tick_in_micro_seconds / recording_time)
        return math.ceil(n_entries * RECORDING_SIZE_PER_ENTRY)

    def get_recorded_data(self, placement, buffer_manager):
        """ Get data from SDRAM given placement and buffer manager

        :param placement: the location on machine to get data from
        :type placement: ~pacman.model.placements.Placement
        :param buffer_manager: the buffer manager that might have data
        :type buffer_manager: \
            ~spinn_front_end_common.interface.buffer_management.BufferManager
        :return: results, an array with 1 dimension of uint32 values
        :rtype: numpy.ndarray
        """
        # for buffering output info is taken form the buffer manager
        # get raw data as a byte array
        record_raw, data_missing = buffer_manager.get_data_by_placement(
            placement, self._SAMPLE_RECORDING_CHANNEL)
        if data_missing:
            logger.warning(
                "Chip Power monitor has lost data on chip({}, {})",
                placement.x, placement.y)

        results = (
            numpy.frombuffer(record_raw, dtype="uint32").reshape(-1, 18) /
            self.n_samples_per_recording)
        return results
