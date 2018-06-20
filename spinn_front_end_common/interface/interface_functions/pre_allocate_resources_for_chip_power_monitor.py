# pacman imports
from pacman.model.resources import CoreResource
from pacman.model.resources import PreAllocatedResourceContainer
from pacman.model.resources import SpecificChipSDRAMResource

# front end common imports
from spinn_front_end_common.utility_models import \
    ChipPowerMonitorMachineVertex as ChipPowerMonitor

# utils
from spinn_utilities.progress_bar import ProgressBar


class PreAllocateResourcesForChipPowerMonitor(object):
    """ Adds chip power monitor resources as required for a machine
    """

    def __call__(
            self, machine, n_machine_time_steps, n_samples_per_recording,
            sampling_frequency, time_scale_factor, machine_time_step,
            pre_allocated_resources=None):
        """
        :param pre_allocated_resources: other preallocated resources
        :param machine: the SpiNNaker machine as discovered
        :param n_machine_time_steps: the number of machine\
            time steps used by the simulation during this phase
        :param n_samples_per_recording: how many samples between record entries
        :param sampling_frequency: the frequency of sampling
        :param time_scale_factor: the time scale factor
        :param machine_time_step: the machine time step
        :return: preallocated resources
        """
        # pylint: disable=too-many-arguments

        progress_bar = ProgressBar(
            machine.n_chips, "Preallocating resources for chip power monitor")

        # store how much SDRAM the power monitor uses per core
        resources = ChipPowerMonitor.get_resources(
            n_machine_time_steps=n_machine_time_steps,
            n_samples_per_recording=n_samples_per_recording,
            sampling_frequency=sampling_frequency,
            time_scale_factor=time_scale_factor,
            time_step=machine_time_step)

        # for every Ethernet connected chip, get the resources needed by the
        # live packet gatherers
        sdrams = list()
        cores = list()
        for chip in progress_bar.over(machine.chips):
            sdrams.append(
                SpecificChipSDRAMResource(chip, resources.sdram.get_value()))
            cores.append(CoreResource(chip, 1))

        # create pre allocated resource container
        cpm_pre_allocated_resource_container = PreAllocatedResourceContainer(
            specific_sdram_usage=sdrams, core_resources=cores)

        # add other pre allocated resources
        if pre_allocated_resources is not None:
            cpm_pre_allocated_resource_container.extend(
                pre_allocated_resources)

        # return pre allocated resources
        return cpm_pre_allocated_resource_container
