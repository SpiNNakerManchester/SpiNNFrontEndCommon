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

from spinn_utilities.progress_bar import ProgressBar
from pacman.model.resources import (
    CoreResource, PreAllocatedResourceContainer, SpecificChipSDRAMResource)
from spinn_front_end_common.utility_models import (
    ChipPowerMonitorMachineVertex)


class PreAllocateResourcesForChipPowerMonitor(object):
    """ Adds chip power monitor resources as required for a machine.
    """

    def __call__(
            self, machine, n_samples_per_recording,
            sampling_frequency, time_scale_factor, machine_time_step,
            pre_allocated_resources):
        """
        :param ~spinn_machine.Machine machine:
            the SpiNNaker machine as discovered
        :param int n_samples_per_recording:
            how many samples between record entries
        :param int sampling_frequency: the frequency of sampling
        :param int time_scale_factor: the time scale factor
        :param int machine_time_step: the machine time step
        :param pre_allocated_resources: other preallocated resources
        :type pre_allocated_resources:
            ~pacman.model.resources.PreAllocatedResourceContainer
        :return: preallocated resources
        :rtype: ~pacman.model.resources.PreAllocatedResourceContainer
        """
        # pylint: disable=too-many-arguments

        progress_bar = ProgressBar(
            machine.n_chips, "Preallocating resources for chip power monitor")

        # store how much SDRAM the power monitor uses per core
        resources = ChipPowerMonitorMachineVertex.get_resources(
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
                SpecificChipSDRAMResource(chip, resources.sdram))
            cores.append(CoreResource(chip, 1))

        # note what has been preallocated
        allocated = PreAllocatedResourceContainer(
            specific_sdram_usage=sdrams, core_resources=cores)
        allocated.extend(pre_allocated_resources)
        return allocated
