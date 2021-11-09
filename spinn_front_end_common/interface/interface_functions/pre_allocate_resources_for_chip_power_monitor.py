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

from spinn_utilities.config_holder import get_config_int
from spinn_front_end_common.utility_models import (
    ChipPowerMonitorMachineVertex)


def preallocate_resources_for_chip_power_monitor(pre_allocated_resources):
    """  Adds chip power monitor resources as required

    :param int sampling_frequency: the frequency of sampling
    :param pre_allocated_resources: other preallocated resources
    :type pre_allocated_resources:
        ~pacman.model.resources.PreAllocatedResourceContainer
    :return: preallocated resources
    :rtype: ~pacman.model.resources.PreAllocatedResourceContainer
    """
    # pylint: disable=too-many-arguments

    sampling_frequency,  = get_config_int(
        "EnergyMonitor", "sampling_frequency"),
    # store how much SDRAM the power monitor uses per core
    resources = ChipPowerMonitorMachineVertex.get_resources(
        sampling_frequency=sampling_frequency)
    pre_allocated_resources.add_sdram_all(resources.sdram)
    pre_allocated_resources.add_cores_all(1)
