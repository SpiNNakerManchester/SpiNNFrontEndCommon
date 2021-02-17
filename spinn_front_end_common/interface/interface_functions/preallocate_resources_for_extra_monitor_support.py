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
    """ Allocates resources for the extra monitors.
    """
    def __call__(
            self, machine, pre_allocated_resources,
            n_cores_to_allocate=1):
        """
        :param ~spinn_machine.Machine machine: SpiNNaker machine object
        :param pre_allocated_resources: resources already preallocated
        :type pre_allocated_resources:
            ~pacman.model.resources.PreAllocatedResourceContainer
        :param int n_cores_to_allocate: how many gatherers to use per chip
        :rtype: ~pacman.model.resources.PreAllocatedResourceContainer
        """

        progress = ProgressBar(
            len(list(machine.ethernet_connected_chips)) + machine.n_chips,
            "Preallocating resources for Extra Monitor support vertices")

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

        # note what has been preallocated
        allocated = PreAllocatedResourceContainer(
            specific_sdram_usage=sdrams, core_resources=cores,
            specific_iptag_resources=tags)
        allocated.extend(pre_allocated_resources)
        return allocated

    @staticmethod
    def _handle_second_monitor_support(cores, sdrams, machine, progress):
        """ Adds the second monitor preallocations, which reflect the\
            reinjector and data extractor support

        :param list(~.CoreResource) cores: the storage of core requirements
        :param ~.Machine machine: the spinnMachine instance
        :param ~.ProgressBar progress: the progress bar to operate one
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

        :param list(~.SpecificChipSDRAMResource) sdrams:
            the preallocated SDRAM requirement for these vertices
        :param list(~.CoreResource) cores:
            the preallocated cores requirement for these vertices
        :param list(~.SpecificBoardIPtagResource) tags:
            the preallocated tags requirement for these vertices
        :param ~.Machine machine: the spinnMachine instance
        :param ~.ProgressBar progress: the progress bar to update as needed
        :param int n_cores_to_allocate:
            how many packet gathers to allocate per chip
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
