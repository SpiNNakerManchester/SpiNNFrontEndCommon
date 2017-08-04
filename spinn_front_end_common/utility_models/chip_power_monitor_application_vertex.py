from pacman.executor.injection_decorator import inject_items
from pacman.model.graphs.application import ApplicationVertex

from spinn_front_end_common.abstract_models.\
    abstract_generates_data_specification import \
    AbstractGeneratesDataSpecification
from spinn_front_end_common.abstract_models.\
    abstract_has_associated_binary import \
    AbstractHasAssociatedBinary
from spinn_front_end_common.utility_models.\
    chip_power_monitor_machine_vertex import ChipPowerMonitorMachineVertex

from spinn_utilities.overrides import overrides


class ChipPowerMonitorApplicationVertex(
        ApplicationVertex, AbstractHasAssociatedBinary,
        AbstractGeneratesDataSpecification):
    """ class for representing idle time recording code in a application graph.
    """

    def __init__(
            self, label, constraints, n_samples_per_recording,
            sampling_frequency):
        """ chip power monitor application vertex constructor

        :param label: vertex label
        :param constraints: constraints for the vertex
        :param n_samples_per_recording: how many samples to take before /
            recording to sdram the total
        :param sampling_frequency: how many microseconds between sampling
        """
        ApplicationVertex.__init__(self, label, constraints, 1)
        self._n_samples_per_recording = n_samples_per_recording
        self._sampling_frequency = sampling_frequency

    @property
    @overrides(ApplicationVertex.n_atoms)
    def n_atoms(self):
        return 1

    @overrides(ApplicationVertex.create_machine_vertex)
    def create_machine_vertex(self, vertex_slice, resources_required,
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
                   "n_machine_time_steps": "TotalMachineTimeSteps",
                   "ip_tags": "MemoryIpTags"})
    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification,
        additional_arguments={
            "machine_time_step", "time_scale_factor", "n_machine_time_steps",
            "ip_tags"})
    def generate_data_specification(
            self, spec, placement, machine_time_step, time_scale_factor,
            n_machine_time_steps, ip_tags):
        # generate spec for the machine vertex
        placement.vertex._generate_data_specification(
            spec, machine_time_step, time_scale_factor, n_machine_time_steps,
            ip_tags)

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ChipPowerMonitorMachineVertex.binary_start_type()

    @overrides(ApplicationVertex.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(self, vertex_slice):
        return self._get_resources_used_by_atoms(vertex_slice)

    @inject_items({
        "n_machine_time_steps": "TotalMachineTimeSteps",
        "machine_time_step": "MachineTimeStep",
        "time_scale_factor": "TimeScaleFactor"})
    def _get_resources_used_by_atoms(
            self, vertex_slice, n_machine_time_steps, time_scale_factor,
            machine_time_step):
        return ChipPowerMonitorMachineVertex.get_resources(
            n_machine_time_steps, machine_time_step, time_scale_factor,
            self._n_samples_per_recording, self._sampling_frequency)
