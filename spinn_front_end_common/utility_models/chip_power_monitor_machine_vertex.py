# Copyright (c) 2017-2022 The University of Manchester
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
from enum import IntEnum
import numpy
from spinn_utilities.config_holder import get_config_int
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from data_specification.enums import DataType
from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import VariableSDRAM
from spinn_front_end_common.abstract_models import (
    AbstractGeneratesDataSpecification, AbstractHasAssociatedBinary)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.buffer_management import (
    recording_utilities)
from spinn_front_end_common.interface.buffer_management.buffer_models import (
    AbstractReceiveBuffersToHost)
from spinn_front_end_common.interface.provenance import ProvenanceWriter
from spinn_front_end_common.utilities.constants import (
    SYSTEM_BYTES_REQUIREMENT, SIMULATION_N_BYTES, BYTES_PER_WORD)
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utilities.helpful_functions import (
    locate_memory_region_for_placement)
from spinn_front_end_common.interface.simulation.simulation_utilities import (
    get_simulation_header_array)

logger = FormatAdapter(logging.getLogger(__name__))
BINARY_FILE_NAME = "chip_power_monitor.aplx"
PROVENANCE_KEY = "Power_Monitor_Total_Activity_Count"

RECORDING_SIZE_PER_ENTRY = 18 * BYTES_PER_WORD
DEFAULT_MALLOCS_USED = 3
CONFIG_SIZE_IN_BYTES = 2 * BYTES_PER_WORD


class ChipPowerMonitorMachineVertex(
        MachineVertex, AbstractHasAssociatedBinary,
        AbstractGeneratesDataSpecification, AbstractReceiveBuffersToHost):
    """ Machine vertex for C code representing functionality to record\
        idle times in a machine graph.
    """
    __slots__ = [
        "_sampling_frequency"]

    class _REGIONS(IntEnum):
        # data regions
        SYSTEM = 0
        CONFIG = 1
        RECORDING = 2

    #: which channel in the recording region has the recorded samples
    _SAMPLE_RECORDING_CHANNEL = 0

    def __init__(
            self, label, sampling_frequency, app_vertex=None,
            vertex_slice=None):
        """
        :param str label: vertex label
        :param int sampling_frequency: how often to sample, in microseconds
        :param ChipPowerMonitor app_vertex: associated application vertex
        :param ~pacman.model.graphs.common.Slice vertex_slice:
        """
        super().__init__(
            label=label, app_vertex=app_vertex, vertex_slice=vertex_slice)
        self._sampling_frequency = sampling_frequency

    @property
    def sampling_frequency(self):
        """ how often to sample, in microseconds

        :rtype: int
        """
        return self._sampling_frequency

    @property
    @overrides(MachineVertex.sdram_required)
    def sdram_required(self):
        return self.get_resources(self._sampling_frequency)

    @staticmethod
    def get_resources(sampling_frequency):
        """ Get the resources used by this vertex

        :param float sampling_frequency:
        :rtype: ~pacman.model.resources.VariableSDRAM
        """
        # The number of sample per step does not have to be an int
        samples_per_step = (FecDataView.get_hardware_time_step_us() /
                            sampling_frequency)
        n_samples_per_recording = get_config_int(
            "EnergyMonitor", "n_samples_per_recording_entry")
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

        return VariableSDRAM(with_overflow, per_timestep)

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return BINARY_FILE_NAME

    @staticmethod
    def binary_file_name():
        """ Return the string binary file name

        :rtype: str
        """
        return BINARY_FILE_NAME

    @overrides(AbstractGeneratesDataSpecification.generate_data_specification)
    def generate_data_specification(
            self, spec, placement,  # @UnusedVariable
            ):
        """ Supports the application vertex calling this directly

        :param ~data_specification.DataSpecificationGenerator spec: data spec
        :param int data_n_time_steps: timesteps to reserve data for
        """
        spec.comment("\n*** Spec for ChipPowerMonitor Instance ***\n\n")

        # Construct the data images needed for the Neuron:
        self._reserve_memory_regions(spec)
        self._write_setup_info(spec)
        self._write_configuration_region(spec)

        # End-of-Spec:
        spec.end_specification()

    def _write_configuration_region(self, spec):
        """ Write the data needed by the C code to configure itself

        :param ~data_specification.DataSpecificationGenerator spec:
            spec object
        """
        spec.switch_write_focus(region=self._REGIONS.CONFIG)
        n_samples_per_recording = get_config_int(
            "EnergyMonitor", "n_samples_per_recording_entry")
        spec.write_value(n_samples_per_recording, data_type=DataType.UINT32)
        spec.write_value(self._sampling_frequency, data_type=DataType.UINT32)

    def _write_setup_info(self, spec):
        """ Writes the system data as required.

        :param ~data_specification.DataSpecificationGenerator spec:
            the DSG spec writer
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

    def _reserve_memory_regions(self, spec):
        """ Reserve the DSG memory regions as required

        :param ~data_specification.DataSpecificationGenerator spec:
            the DSG specification to reserve in
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
    def get_recording_region_base_address(self, placement):
        return locate_memory_region_for_placement(
            placement, self._REGIONS.RECORDING)

    @overrides(AbstractReceiveBuffersToHost.get_recorded_region_ids)
    def get_recorded_region_ids(self):
        return [0]

    def _deduce_sdram_requirements_per_timer_tick(self):
        """ Deduce SDRAM usage per timer tick

        :return: the SDRAM usage
        :rtype: int
        """
        recording_time = \
            self._sampling_frequency * get_config_int(
                "EnergyMonitor", "n_samples_per_recording_entry")
        n_entries = math.floor(FecDataView.get_hardware_time_step_us() /
                               recording_time)
        return int(math.ceil(n_entries * RECORDING_SIZE_PER_ENTRY))

    def get_recorded_data(self, placement):
        """ Get data from SDRAM given placement and buffer manager. \
            Also arranges for provenance data to be available.

        :param ~pacman.model.placements.Placement placement:
            the location on machine to get data from
        :return: results, an array with 1 dimension of uint32 values
        :rtype: ~numpy.ndarray
        """
        # for buffering output info is taken form the buffer manager
        # get raw data as a byte array
        buffer_manager = FecDataView.get_buffer_manager()
        record_raw, data_missing = buffer_manager.get_data_by_placement(
            placement, self._SAMPLE_RECORDING_CHANNEL)
        if data_missing:
            logger.warning(
                "Chip Power monitor has lost data on chip({}, {})",
                placement.x, placement.y)

        n_samples_per_recording = get_config_int(
            "EnergyMonitor", "n_samples_per_recording_entry")
        results = (
            numpy.frombuffer(record_raw, dtype="uint32").reshape(-1, 18) /
            n_samples_per_recording)
        activity_count = int(
            numpy.frombuffer(record_raw, dtype="uint32").sum())
        with ProvenanceWriter() as db:
            db.insert_monitor(
                placement.x, placement.y, PROVENANCE_KEY, activity_count)
        return results
