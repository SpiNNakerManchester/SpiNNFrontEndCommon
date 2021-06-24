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

from spinn_utilities.config_holder import get_config_int
from spinn_utilities.progress_bar import ProgressBar
from spinn_machine.machine import Machine
from pacman.model.resources import (ConstantSDRAM)
from spinn_front_end_common.interface.interface_functions. \
    machine_bit_field_router_compressor import (
        SIZE_OF_SDRAM_ADDRESS_IN_BYTES)


class PreAllocateForBitFieldRouterCompressor(object):
    """ Preallocates resources required for bitfield router compression.
    """

    def __call__(self, machine, pre_allocated_resources):
        """
        :param ~spinn_machine.Machine machine:
            the SpiNNaker machine as discovered
        :param pre_allocated_resources: other preallocated resources
        :type pre_allocated_resources:
            ~pacman.model.resources.PreAllocatedResourceContainer
        :return: preallocated resources
        :rtype: ~pacman.model.resources.PreAllocatedResourceContainer
        """

        progress_bar = ProgressBar(
            1, "Preallocating resources for bit field compressor")

        # for every Ethernet connected chip, get the resources needed by the
        # live packet gatherers
        sdram_to_pre_alloc_for_bit_fields = get_config_int(
            "Mapping",
            "router_table_compression_with_bit_field_pre_alloced_sdram")
        sdram = ConstantSDRAM(
            (SIZE_OF_SDRAM_ADDRESS_IN_BYTES * Machine.max_cores_per_chip()) +
            sdram_to_pre_alloc_for_bit_fields)

        # note what has been preallocated
        pre_allocated_resources.add_sdram_all(sdram)

        progress_bar.end()
        return pre_allocated_resources
