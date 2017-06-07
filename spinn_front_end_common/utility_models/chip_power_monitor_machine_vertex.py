from enum import Enum
import math

from data_specification.enums.data_type import DataType
from pacman.executor.injection_decorator import inject_items
from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import ResourceContainer, SDRAMResource, \
    CPUCyclesPerTickResource, DTCMResource

from spinn_front_end_common.abstract_models.\
    abstract_generates_data_specification import \
    AbstractGeneratesDataSpecification
from spinn_front_end_common.abstract_models.\
    abstract_has_associated_binary import \
    AbstractHasAssociatedBinary
from spinn_front_end_common.interface.buffer_management import \
    recording_utilities
from spinn_front_end_common.interface.buffer_management.buffer_models.\
    abstract_receive_buffers_to_host import \
    AbstractReceiveBuffersToHost
from spinn_front_end_common.utilities import globals_variables
from spinn_front_end_common.utilities.utility_objs.\
    executable_start_type import \
    ExecutableStartType
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.interface.simulation import simulation_utilities

from spinn_utilities.overrides import overrides


class ChipPowerMonitorMachineVertex(
        MachineVertex, AbstractHasAssociatedBinary,
        AbstractGeneratesDataSpecification, AbstractReceiveBuffersToHost):

    CHIP_POWER_MONITOR_REGIONS = Enum(
        value="CHIP_POWER_MONITOR_REGIONS",
        names=[('SYSTEM', 0),
               ('CONFIG', 1),
               ('RECORDING', 2)])
    DEFAULT_MALLOCS_USED = 3
    CONFIG_SIZE_IN_BYTES = 8
    RECORDING_SIZE_PER_ENTRY = 18 * 4

    def __init__(
            self, label, constraints, n_samples_per_recording,
            sampling_frequency):
        """

        :param label:
        :param constraints:
        :param n_samples_per_recording: how may samples between recording entry
        :type n_samples_per_recording: int
        :param sampling_frequency: how often to sample
        :type sampling_frequency: ???????
        """
        MachineVertex.__init__(self, label=label, constraints=constraints)
        self._n_samples_per_recording = n_samples_per_recording
        self._sampling_frequency = sampling_frequency

    @property
    @overrides(MachineVertex.resources_required)
    @inject_items({
        "n_machine_time_steps": "TotalMachineTimeSteps",
        "machine_time_step": "MachineTimeStep",
        "time_scale_factor": "TimeScaleFactor"
    })
    def resources_required(self, n_machine_time_steps, machine_time_step,
                           time_scale_factor):
        return self.get_resources(
            n_machine_time_steps, machine_time_step, time_scale_factor,
            self._n_samples_per_recording, self._sampling_frequency)

    @staticmethod
    def get_resources(
            n_machine_time_steps, time_step, time_scale_factor,
            n_samples_per_recording, sampling_frequency):
        """

        :return:
        """
        # get config
        config = globals_variables.get_simulator().config

        # get recording params
        minimum_buffer_sdram = config.getint(
            "Buffers", "minimum_buffer_sdram")
        using_auto_pause_and_resume = config.getboolean(
            "Buffers", "use_auto_pause_and_resume")
        receive_buffer_host = config.get("Buffers", "receive_buffer_host")
        receive_buffer_port = helpful_functions.read_config_int(
            config, "Buffers", "receive_buffer_port")

        # figure max buffer size
        max_buffer_size = 0
        if config.getboolean("Buffers", "enable_buffered_recording"):
            max_buffer_size = config.getint(
                "Buffers", "spike_buffer_size")
        maximum_sdram_for_buffering = [max_buffer_size]

        # figure recording size for max run
        n_recording_entries = math.ceil(
            (sampling_frequency /
             (n_machine_time_steps * time_step * time_scale_factor)) /
            n_samples_per_recording)
        recording_size = (
            ChipPowerMonitorMachineVertex.RECORDING_SIZE_PER_ENTRY *
            n_recording_entries)

        container = ResourceContainer(
            sdram=SDRAMResource(
                ChipPowerMonitorMachineVertex.sdram_calculation()),
            cpu_cycles=CPUCyclesPerTickResource(100),
            dtcm=DTCMResource(100))
        recording_sizes = recording_utilities.get_recording_region_sizes(
            [recording_size, 1], n_machine_time_steps, minimum_buffer_sdram,
            maximum_sdram_for_buffering, using_auto_pause_and_resume)
        container.extend(recording_utilities.get_recording_resources(
            recording_sizes, receive_buffer_host, receive_buffer_port))
        return container

    @staticmethod
    def sdram_calculation():
        """ calculates the sdram requirements of the vertex

        :return: int
        """
        return constants.SYSTEM_BYTES_REQUIREMENT + \
            ChipPowerMonitorMachineVertex.CONFIG_SIZE_IN_BYTES + \
            ChipPowerMonitorMachineVertex.DEFAULT_MALLOCS_USED * \
            constants.SARK_PER_MALLOC_SDRAM_USAGE

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return ChipPowerMonitorMachineVertex.binary_file_name()

    @staticmethod
    def binary_file_name():
        """ returns the string binary file name

        :return:
        """
        return "chip_power_monitor.aplx"

    @overrides(AbstractGeneratesDataSpecification.generate_data_specification,
               additional_arguments={"machine_time_step", "time_scale_factor"})
    def generate_data_specification(
            self, spec, placement, machine_time_step, time_scale_factor):
        spec.comment("\n*** Spec for ChipPowerMonitor Instance ***\n\n")

        # Construct the data images needed for the Neuron:
        self._reserve_memory_regions(spec)
        self._write_setup_info(spec, machine_time_step, time_scale_factor)
        self._write_configuration_region(spec)

        # End-of-Spec:
        spec.end_specification()

    def _write_configuration_region(self, spec):
        """ writes the data needed by the c code to configure itself

        :param spec: spec object
        :rtype: None
        """
        spec.switch_write_focus(
            region=ChipPowerMonitorMachineVertex.CHIP_POWER_MONITOR_REGIONS.
            CONFIG.value)
        spec.write_value(self._n_samples_per_recording,
                         data_type=DataType.UINT32)
        spec.write_value(self._sampling_frequency, data_type=DataType.UINT32)

    def _write_setup_info(self, spec, machine_time_step, time_scale_factor):
        """ writes the system data as required

        :param spec: the dsg spec writer
        :param machine_time_step: the machine time step
        :param time_scale_factor: the time scale factor
        :rtype: None
        """
        spec.switch_write_focus(
            region=(
                ChipPowerMonitorMachineVertex.CHIP_POWER_MONITOR_REGIONS.
                SYSTEM.value))
        spec.write_array(simulation_utilities.get_simulation_header_array(
            self.get_binary_file_name(), machine_time_step, time_scale_factor))

    def _reserve_memory_regions(self, spec):
        """ reserve the dsg memory regions as required

        :param spec: the dsg specification to reserve in
        :rtype: None
        """
        spec.comment("\nReserving memory space for data regions:\n\n")

        # Reserve memory:
        spec.reserve_memory_region(
            region=(
                ChipPowerMonitorMachineVertex.CHIP_POWER_MONITOR_REGIONS.
                SYSTEM.value),
            size=constants.SYSTEM_BYTES_REQUIREMENT,
            label='system')
        spec.reserve_memory_region(
            region=(
                ChipPowerMonitorMachineVertex.CHIP_POWER_MONITOR_REGIONS.
                CONFIG.value),
            size=self.CONFIG_SIZE_IN_BYTES, label='config')
        spec.reserve_memory_region(
            region=(ChipPowerMonitorMachineVertex.
                    CHIP_POWER_MONITOR_REGIONS.RECORDING.value),
            size=recording_utilities.get_recording_header_size(1),
            label="Recording")

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return self.binary_start_type()

    @staticmethod
    def binary_start_type():
        """ static method to allow app verts to use this

        :return:
        """
        return ExecutableStartType.USES_SIMULATION_INTERFACE

    @overrides(AbstractReceiveBuffersToHost.get_recording_region_base_address)
    def get_recording_region_base_address(self, txrx, placement):
        return helpful_functions.locate_memory_region_for_placement(
            placement,
            self._CHIP_POWER_MONITOR_REGIONS.RECORDING.value,
            txrx)

    @overrides(AbstractReceiveBuffersToHost.get_recorded_region_ids)
    def get_recorded_region_ids(self):
        return [0]

    @overrides(AbstractReceiveBuffersToHost.get_n_timesteps_in_buffer_space)
    def get_n_timesteps_in_buffer_space(self, buffer_space, machine_time_step):
        return recording_utilities.get_n_timesteps_in_buffer_space(
            buffer_space, [self._buffered_sdram_per_timestep])

    @overrides(AbstractReceiveBuffersToHost.get_minimum_buffer_sdram_usage)
    def get_minimum_buffer_sdram_usage(self):
        return self._minimum_buffer_sdram
