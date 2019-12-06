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

import logging
import os
import struct
from spinn_utilities.log import FormatAdapter
from spinn_utilities.progress_bar import ProgressBar
from data_specification.constants import MAX_MEM_REGIONS
from spinn_front_end_common.utilities.constants import BYTES_PER_WORD

logger = FormatAdapter(logging.getLogger(__name__))
_ONE_WORD = struct.Struct("<I")
MEM_MAP_SUBDIR_NAME = "memory_map_reports"
MEM_MAP_FILENAME = "memory_map_from_processor_{0:d}_{1:d}_{2:d}.txt"


class MemoryMapOnHostChipReport(object):
    """ Report on memory usage.
    """

    def __call__(self, report_default_directory, dsg_targets, transceiver):
        """ Creates a report that states where in SDRAM each region is \
            (read from machine)

        :param report_default_directory: the folder where reports are written
        :param dsg_targets: the map between placement and file writer
        :param transceiver: the spinnMan instance
        :rtype: None
        """

        directory_name = os.path.join(
            report_default_directory, MEM_MAP_SUBDIR_NAME)
        if not os.path.exists(directory_name):
            os.makedirs(directory_name)

        progress = ProgressBar(dsg_targets, "Writing memory map reports")
        for (x, y, p) in progress.over(dsg_targets):
            file_name = os.path.join(
                directory_name, MEM_MAP_FILENAME.format(x, y, p))
            try:
                with open(file_name, "w") as f:
                    self._describe_mem_map(f, transceiver, x, y, p)
            except IOError:
                logger.exception("Generate_placement_reports: Can't open file"
                                 " {} for writing.", file_name)

    def _describe_mem_map(self, f, txrx, x, y, p):
        # pylint: disable=too-many-arguments
        # Read the memory map data from the given core
        user_0_addr = txrx.get_user_0_register_address_from_core(p)
        pointer_table_addr = self._get_app_pointer_table(
            txrx, x, y, user_0_addr)
        memmap_data = txrx.read_memory(
            x, y, pointer_table_addr, BYTES_PER_WORD * MAX_MEM_REGIONS)

        # Convert the map to a human-readable description
        f.write("On chip data specification executor\n\n")
        for i in range(MAX_MEM_REGIONS):
            region_address, = _ONE_WORD.unpack_from(
                memmap_data, i * BYTES_PER_WORD)
            f.write("Region {0:d}:\n\t start address: 0x{1:x}\n\n".format(
                i, region_address))

    def _get_app_pointer_table(self, txrx, x, y, table_pointer):
        encoded_address = txrx.read_memory(x, y, table_pointer, BYTES_PER_WORD)
        return _ONE_WORD.unpack_from(encoded_address)[0] + 2 * BYTES_PER_WORD
