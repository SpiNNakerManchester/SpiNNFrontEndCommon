# Copyright (c) 2019-2020 The University of Manchester
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
    SpecificChipSDRAMResource, PreAllocatedResourceContainer)
from spinn_front_end_common.interface.interface_functions. \
    machine_bit_field_router_compressor import (
        SIZE_OF_SDRAM_ADDRESS_IN_BYTES)


class PreAllocateForBitFieldRouterCompressor(object):
    """ Preallocates resources required for bitfield router compression.
    """

    def __call__(self, machine, sdram_to_pre_alloc_for_bit_fields,
                 pre_allocated_resources):
        """
        :param ~spinn_machine.Machine machine:
            the SpiNNaker machine as discovered
        :param int sdram_to_pre_alloc_for_bit_fields:
            SDRAM end user managed to help with bitfield compressions.
            Basically ensuring some SDRAM is available in the case where there
            is no SDRAM available to steal/use.
        :param pre_allocated_resources: other preallocated resources
        :type pre_allocated_resources:
            ~pacman.model.resources.PreAllocatedResourceContainer
        :return: preallocated resources
        :rtype: ~pacman.model.resources.PreAllocatedResourceContainer
        """

        progress_bar = ProgressBar(
            machine.n_chips,
            "Preallocating resources for bit field compressor")

        # for every Ethernet connected chip, get the resources needed by the
        # live packet gatherers
        sdrams = list()

        for chip in progress_bar.over(machine.chips):
            sdrams.append(SpecificChipSDRAMResource(
                chip,
                (SIZE_OF_SDRAM_ADDRESS_IN_BYTES * chip.n_user_processors) +
                sdram_to_pre_alloc_for_bit_fields))

        # note what has been preallocated
        allocated = PreAllocatedResourceContainer(
            specific_sdram_usage=sdrams)
        allocated.extend(pre_allocated_resources)
        return allocated
