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
    SpecificChipSDRAMResource, CoreResource,
    PreAllocatedResourceContainer, SpecificBoardIPtagResource)
from spinn_front_end_common.utility_models import (
    ExtraMonitorSupportMachineVertex)
from spinn_front_end_common.utility_models import (
    DataSpeedUpPacketGatherMachineVertex)


class PreAllocateResourcesForExtraMonitorSupport(object):
    def __call__(
            self, machine, pre_allocated_resources=None,
            n_cores_to_allocate=1):
        """
        :param machine: SpiNNaker machine object
        :param pre_allocated_resources: resources already preallocated
        :param n_cores_to_allocate: how many gatherers to use
        """

        progress = ProgressBar(
            len(list(machine.ethernet_connected_chips)) + machine.n_chips,
            "Pre allocating resources for Extra Monitor support vertices")

        sdrams = list()
        cores = list()
        tags = list()

        # add resource requirements for the gatherers on each Ethernet
        # connected chip. part of data extraction
        self._handle_packet_gathering_support(
            sdrams, cores, tags, machine, progress, n_cores_to_allocate)

        # add resource requirements for re-injector and reader for data
        # extractor
        self._handle_second_monitor_support(cores, sdrams, machine, progress)

        # create pre allocated resource container
        extra_monitor_pre_allocations = PreAllocatedResourceContainer(
            specific_sdram_usage=sdrams, core_resources=cores,
            specific_iptag_resources=tags)

        # add other pre allocated resources
        if pre_allocated_resources is not None:
            extra_monitor_pre_allocations.extend(pre_allocated_resources)

        # return pre allocated resources
        return extra_monitor_pre_allocations

    @staticmethod
    def _handle_second_monitor_support(cores, sdrams, machine, progress):
        """ Adds the second monitor preallocations, which reflect the\
            reinjector and data extractor support

        :param cores: the storage of core requirements
        :param machine: the spinnMachine instance
        :param progress: the progress bar to operate one
        :rtype: None
        """
        extra_usage = \
            ExtraMonitorSupportMachineVertex.static_resources_required()
        for chip in progress.over(machine.chips):
            cores.append(CoreResource(chip=chip, n_cores=1))
            sdrams.append(SpecificChipSDRAMResource(
                chip=chip, sdram_usage=extra_usage.sdram))

    @staticmethod
    def _handle_packet_gathering_support(
            sdrams, cores, tags, machine, progress, n_cores_to_allocate):
        """ Adds the packet gathering functionality tied into the data\
            extractor within each chip

        :param sdrams: the preallocated SDRAM requirement for these vertices
        :param cores: the preallocated cores requirement for these vertices
        :param tags: the preallocated tags requirement for these vertices
        :param machine: the spinnMachine instance
        :param progress: the progress bar to update as needed
        :param n_cores_to_allocate: \
            how many packet gathers to allocate per chip
        :rtype: None
        """
        # pylint: disable=too-many-arguments

        # get resources from packet gatherer
        resources = DataSpeedUpPacketGatherMachineVertex.\
            static_resources_required()

        # locate Ethernet connected chips that the vertices reside on
        for ethernet_connected_chip in \
                progress.over(machine.ethernet_connected_chips,
                              finish_at_end=False):
            # do resources. SDRAM, cores, tags
            sdrams.append(SpecificChipSDRAMResource(
                chip=ethernet_connected_chip,
                sdram_usage=resources.sdram))
            cores.append(CoreResource(
                chip=ethernet_connected_chip, n_cores=n_cores_to_allocate))
            tags.append(SpecificBoardIPtagResource(
                board=ethernet_connected_chip.ip_address,
                ip_address=resources.iptags[0].ip_address,
                port=resources.iptags[0].port,
                strip_sdp=resources.iptags[0].strip_sdp,
                tag=resources.iptags[0].tag,
                traffic_identifier=resources.iptags[0].traffic_identifier))
