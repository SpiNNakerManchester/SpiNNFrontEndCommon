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
    ConstantSDRAM, CoreResource, PreAllocatedResourceContainer,
    SpecificChipSDRAMResource, SpecificBoardIPtagResource)
from spinn_front_end_common.utility_models import (
    LivePacketGatherMachineVertex)


class PreAllocateResourcesForLivePacketGatherers(object):
    """ Adds Live Packet Gatherer resources as required for a machine.
    """

    def __call__(
            self, live_packet_gatherer_parameters, machine,
            pre_allocated_resources):
        """
        :param live_packet_gatherer_parameters:
            the LPG parameters requested by the script
        :type live_packet_gatherer_parameters:
            dict(LivePacketGatherParameters,
            list(tuple(~pacman.model.graphs.AbstractVertex, list(str))))
        :param ~spinn_machine.Machine machine:
            the SpiNNaker machine as discovered
        :param pre_allocated_resources: other preallocated resources
        :type pre_allocated_resources:
            ~pacman.model.resources.PreAllocatedResourceContainer
        :return: preallocated resources
        :rtype: ~pacman.model.resources.PreAllocatedResourceContainer
        """

        progress = ProgressBar(
            len(machine.ethernet_connected_chips),
            "Preallocating resources for Live Recording")

        # store how much SDRAM the LPG uses per core
        sdram_requirement = LivePacketGatherMachineVertex.get_sdram_usage()

        # for every Ethernet connected chip, get the resources needed by the
        # live packet gatherers
        sdrams = list()
        cores = list()
        iptags = list()
        for chip in progress.over(machine.ethernet_connected_chips):
            self._add_chip_lpg_reqs(
                live_packet_gatherer_parameters, chip, sdram_requirement,
                sdrams, cores, iptags)

        # note what has been preallocated
        allocated = PreAllocatedResourceContainer(
            specific_sdram_usage=sdrams, core_resources=cores,
            specific_iptag_resources=iptags)
        allocated.extend(pre_allocated_resources)
        return allocated

    @staticmethod
    def _add_chip_lpg_reqs(
            lpg_parameters, chip, lpg_sdram, sdrams, cores, iptags):
        """
        :param lpg_parameters:
        :type lpg_parameters:
            dict(LivePacketGatherParameters,
            list(tuple(~.AbstractVertex, list(str))))
        :param ~.Chip chip:
        :param int lpg_sdram:
        :param list(~.SpecificChipSDRAMResource) sdrams:
        :param list(~.CoreResource) cores:
        :param list(~.SpecificBoardIPtagResource) iptags:
        """
        # pylint: disable=too-many-arguments
        sdram_reqs = 0
        core_reqs = 0

        for lpg_params in lpg_parameters:
            if (lpg_params.board_address is None or
                    lpg_params.board_address == chip.ip_address):
                sdram_reqs += lpg_sdram
                core_reqs += 1
                iptags.append(SpecificBoardIPtagResource(
                    board=chip.ip_address,
                    ip_address=lpg_params.hostname, port=lpg_params.port,
                    strip_sdp=lpg_params.strip_sdp, tag=lpg_params.tag,
                    traffic_identifier=(
                        LivePacketGatherMachineVertex.TRAFFIC_IDENTIFIER)))

        if sdram_reqs:
            sdrams.append(SpecificChipSDRAMResource(
                chip, ConstantSDRAM(sdram_reqs)))
        if core_reqs:
            cores.append(CoreResource(chip, core_reqs))
