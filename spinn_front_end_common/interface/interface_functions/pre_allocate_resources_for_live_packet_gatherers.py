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
    SpecificChipSDRAMResource)
from pacman.model.resources.specific_board_iptag_resource import (
    SpecificBoardTagResource)
from spinn_front_end_common.utility_models import (
    LivePacketGatherMachineVertex as
    LPG)


class PreAllocateResourcesForLivePacketGatherers(object):
    """ Adds Live Packet Gatherer resources as required for a machine
    """

    def __call__(
            self, live_packet_gatherer_parameters, machine,
            pre_allocated_resources=None):
        """
        :param live_packet_gatherer_parameters:\
            the LPG parameters requested by the script
        :param previous_allocated_resources: other preallocated resources
        :param machine: the SpiNNaker machine as discovered
        :return: preallocated resources
        """

        progress = ProgressBar(
            len(machine.ethernet_connected_chips),
            "Preallocating resources for Live Recording")

        # store how much SDRAM the LPG uses per core
        sdram_requirement = LPG.get_sdram_usage()

        # for every Ethernet connected chip, get the resources needed by the
        # live packet gatherers
        sdrams = list()
        cores = list()
        iptags = list()
        for chip in progress.over(machine.ethernet_connected_chips):
            self._add_chip_lpg_reqs(
                live_packet_gatherer_parameters, chip, sdram_requirement,
                sdrams, cores, iptags)

        # create preallocated resource container
        lpg_prealloc_resource_container = PreAllocatedResourceContainer(
            specific_sdram_usage=sdrams, core_resources=cores,
            specific_iptag_resources=iptags)

        # add other preallocated resources
        if pre_allocated_resources is not None:
            lpg_prealloc_resource_container.extend(pre_allocated_resources)

        # return preallocated resources
        return lpg_prealloc_resource_container

    @staticmethod
    def _add_chip_lpg_reqs(
            lpg_parameters, chip, lpg_sdram, sdrams, cores, iptags):
        # pylint: disable=too-many-arguments
        sdram_reqs = 0
        core_reqs = 0

        for lpg_params in lpg_parameters:
            if (lpg_params.board_address is None or
                    lpg_params.board_address == chip.ip_address):
                sdram_reqs += lpg_sdram
                core_reqs += 1
                iptags.append(SpecificBoardTagResource(
                    board=chip.ip_address,
                    ip_address=lpg_params.hostname, port=lpg_params.port,
                    strip_sdp=lpg_params.strip_sdp, tag=lpg_params.tag,
                    traffic_identifier=LPG.TRAFFIC_IDENTIFIER))

        if sdram_reqs:
            sdrams.append(SpecificChipSDRAMResource(
                chip, ConstantSDRAM(sdram_reqs)))
        if core_reqs:
            cores.append(CoreResource(chip, core_reqs))
