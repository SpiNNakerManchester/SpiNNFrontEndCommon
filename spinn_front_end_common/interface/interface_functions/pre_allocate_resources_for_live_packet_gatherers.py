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

from pacman.model.resources import ConstantSDRAM, IPtagResource
from spinn_front_end_common.utility_models import (
    LivePacketGatherMachineVertex)


def preallocate_resources_for_live_packet_gatherers(
        live_packet_gatherer_parameters, pre_allocated_resources):
    """ Adds Live Packet Gatherer resources as required for a machine.

    :param live_packet_gatherer_parameters:
        the LPG parameters requested by the script
    :type live_packet_gatherer_parameters:
        dict(LivePacketGatherParameters,
        list(tuple(~pacman.model.graphs.AbstractVertex, list(str))))
    :param pre_allocated_resources: other preallocated resources
    :type pre_allocated_resources:
        ~pacman.model.resources.PreAllocatedResourceContainer
    :return: preallocated resources
    :rtype: ~pacman.model.resources.PreAllocatedResourceContainer
    """

    # store how much SDRAM the LPG uses per core
    sdram = ConstantSDRAM(LivePacketGatherMachineVertex.get_sdram_usage())
    for lpg_params in live_packet_gatherer_parameters:
        pre_allocated_resources.add_sdram_ethernet(sdram)
        pre_allocated_resources.add_cores_ethernet(1)
        pre_allocated_resources.add_iptag_resource(IPtagResource(
            ip_address=lpg_params.hostname, port=lpg_params.port,
            strip_sdp=lpg_params.strip_sdp, tag=lpg_params.tag,
            traffic_identifier=(
                LivePacketGatherMachineVertex.TRAFFIC_IDENTIFIER)))

    # return for testing
    return pre_allocated_resources
