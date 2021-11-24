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

from spinn_front_end_common.utility_models import (
    ExtraMonitorSupportMachineVertex)
from spinn_front_end_common.utility_models import (
    DataSpeedUpPacketGatherMachineVertex)


def pre_allocate_resources_for_extra_monitor_support(pre_allocated_resources):
    """ Allocates resources for the extra monitors.

    :param pre_allocated_resources: resources already preallocated
    :type pre_allocated_resources:
        ~pacman.model.resources.PreAllocatedResourceContainer
    """

    resources = DataSpeedUpPacketGatherMachineVertex.\
        static_resources_required()
    pre_allocated_resources.add_sdram_ethernet(resources.sdram)
    pre_allocated_resources.add_cores_ethernet(1)
    pre_allocated_resources.add_iptag_resource(resources.iptags[0])

    extra_usage = \
        ExtraMonitorSupportMachineVertex.static_resources_required()
    pre_allocated_resources.add_sdram_all(extra_usage.sdram)
    pre_allocated_resources.add_cores_all(1)
