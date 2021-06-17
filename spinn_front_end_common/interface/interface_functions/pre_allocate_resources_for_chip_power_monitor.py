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
from spinn_front_end_common.utility_models import (
    ChipPowerMonitorMachineVertex)


class PreAllocateResourcesForChipPowerMonitor(object):
    """ Adds chip power monitor resources as required for a machine.
    """

    def __call__(
            self, machine,  sampling_frequency, pre_allocated_resources):
        """
        :param ~spinn_machine.Machine machine:
            the SpiNNaker machine as discovered
        :param int sampling_frequency: the frequency of sampling
        :param pre_allocated_resources: other preallocated resources
        :type pre_allocated_resources:
            ~pacman.model.resources.PreAllocatedResourceContainer
        :return: preallocated resources
        :rtype: ~pacman.model.resources.PreAllocatedResourceContainer
        """
        # pylint: disable=too-many-arguments

        progress_bar = ProgressBar(
            1, "Preallocating resources for chip power monitor")

        # store how much SDRAM the power monitor uses per core
        resources = ChipPowerMonitorMachineVertex.get_resources(
            sampling_frequency=sampling_frequency)
        pre_allocated_resources.add_sdram_all(resources.sdram)
        pre_allocated_resources.add_cores_all(1)

        progress_bar.end()
        return pre_allocated_resources
