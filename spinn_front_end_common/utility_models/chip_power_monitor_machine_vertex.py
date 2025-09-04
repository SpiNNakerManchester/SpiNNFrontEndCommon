# Copyright (c) 2017 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import math
import logging
from enum import IntEnum
from typing import List

from spinn_utilities.config_holder import get_config_int
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides

from spinnman.model.enums import ExecutableType

from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import AbstractSDRAM, VariableSDRAM
from pacman.model.placements import Placement

from spinn_front_end_common.abstract_models import (
    AbstractGeneratesDataSpecification, AbstractHasAssociatedBinary)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.buffer_management import (
    recording_utilities)
from spinn_front_end_common.interface.buffer_management.buffer_models import (
    AbstractReceiveBuffersToHost)
from spinn_front_end_common.interface.ds import DataSpecificationGenerator
from spinn_front_end_common.utilities.constants import (
    SYSTEM_BYTES_REQUIREMENT, SIMULATION_N_BYTES, BYTES_PER_WORD)
from spinn_front_end_common.utilities.helpful_functions import (
    locate_memory_region_for_placement)
from spinn_front_end_common.interface.simulation.simulation_utilities import (
    get_simulation_header_array)

logger = FormatAdapter(logging.getLogger(__name__))
BINARY_FILE_NAME = "chip_power_monitor.aplx"
RECORDING_CHANNEL = 0

RECORDING_SIZE_PER_ENTRY = 19 * BYTES_PER_WORD
DEFAULT_MALLOCS_USED = 3
CONFIG_SIZE_IN_BYTES = 2 * BYTES_PER_WORD


class ChipPowerMonitorMachineVertex(
        MachineVertex, AbstractHasAssociatedBinary,
        AbstractGeneratesDataSpecification, AbstractReceiveBuffersToHost):
    """
    Machine vertex for C code representing functionality to record
    idle times in a machine graph.

    .. note::
        This is an unusual machine vertex, in that it has no associated
        application vertex.
    """
    __slots__ = ("__sampling_frequency", "__n_samples_per_recording")

    class _REGIONS(IntEnum):
        # data regions
        SYSTEM = 0
        CONFIG = 1
        RECORDING = 2

    #: which channel in the recording region has the recorded samples
    _SAMPLE_RECORDING_CHANNEL = 0

    def __init__(self, label: str):
        """
        :param label: vertex label
        """
        super().__init__(
            label=label, app_vertex=None, vertex_slice=None)
        self.__sampling_frequency = get_config_int(
            "EnergyMonitor", "sampling_frequency")
        self.__n_samples_per_recording = get_config_int(
            "EnergyMonitor", "n_samples_per_recording_entry")

    @property
    @overrides(MachineVertex.sdram_required)
    def sdram_required(self) -> AbstractSDRAM:
        # The number of sample per step does not have to be an int
        samples_per_step = (FecDataView.get_hardware_time_step_us() /
                            self.__sampling_frequency)
        recording_per_step = samples_per_step / self.__n_samples_per_recording
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

        return VariableSDRAM(math.ceil(with_overflow), math.ceil(per_timestep))

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self) -> str:
        return BINARY_FILE_NAME

    @overrides(AbstractGeneratesDataSpecification.generate_data_specification)
    def generate_data_specification(self, spec: DataSpecificationGenerator,
                                    placement: Placement) -> None:
        spec.comment("\n*** Spec for ChipPowerMonitor Instance ***\n\n")

        # Construct the data images needed for the Neuron:
        self._reserve_memory_regions(spec)
        self._write_setup_info(spec)
        self._write_configuration_region(spec)

        # End-of-Spec:
        spec.end_specification()

    def _write_configuration_region(
            self, spec: DataSpecificationGenerator) -> None:
        """
        Write the data needed by the C code to configure itself.

        :param spec: specification writer
        """
        spec.switch_write_focus(region=self._REGIONS.CONFIG)
        spec.write_value(self.__n_samples_per_recording)
        spec.write_value(self.__sampling_frequency)

    def _write_setup_info(self, spec: DataSpecificationGenerator) -> None:
        """
        Writes the system data as required.

        :param spec: the DSG specification writer
        """
        spec.switch_write_focus(region=self._REGIONS.SYSTEM)
        spec.write_array(get_simulation_header_array(
            self.get_binary_file_name()))

        spec.switch_write_focus(region=self._REGIONS.RECORDING)
        recorded_region_sizes = [
            self._deduce_sdram_requirements_per_timer_tick()
            * FecDataView.get_max_run_time_steps()]
        spec.write_array(recording_utilities.get_recording_header_array(
            recorded_region_sizes))

    def _reserve_memory_regions(
            self, spec: DataSpecificationGenerator) -> None:
        """
        Reserve the DSG memory regions as required.

        :param spec: the DSG specification to reserve in
        """
        spec.comment("\nReserving memory space for data regions:\n\n")

        # Reserve memory:
        spec.reserve_memory_region(
            region=self._REGIONS.SYSTEM,
            size=SIMULATION_N_BYTES,
            label='system')
        spec.reserve_memory_region(
            region=self._REGIONS.CONFIG,
            size=CONFIG_SIZE_IN_BYTES, label='config')
        spec.reserve_memory_region(
            region=self._REGIONS.RECORDING,
            size=recording_utilities.get_recording_header_size(1),
            label="Recording")

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self) -> ExecutableType:
        return self.binary_start_type()

    @staticmethod
    def binary_start_type() -> ExecutableType:
        """
        The type of binary that implements this vertex.

        :return: start-type
        """
        return ExecutableType.USES_SIMULATION_INTERFACE

    @overrides(AbstractReceiveBuffersToHost.get_recording_region_base_address)
    def get_recording_region_base_address(self, placement: Placement) -> int:
        return locate_memory_region_for_placement(
            placement, self._REGIONS.RECORDING)

    @overrides(AbstractReceiveBuffersToHost.get_recorded_region_ids)
    def get_recorded_region_ids(self) -> List[int]:
        return [0]

    def _deduce_sdram_requirements_per_timer_tick(self) -> int:
        """
        Deduce SDRAM usage per timer tick.

        :return: the SDRAM usage
        """
        recording_time = (
            self.__sampling_frequency * self.__n_samples_per_recording)
        n_entries = math.floor(FecDataView.get_hardware_time_step_us() /
                               recording_time)
        return int(math.ceil(n_entries * RECORDING_SIZE_PER_ENTRY))
