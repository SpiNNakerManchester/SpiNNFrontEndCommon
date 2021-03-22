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
from data_specification.constants import MAX_MEM_REGIONS
from spinn_front_end_common.utilities.constants import BYTES_PER_WORD
from spinn_front_end_common.utilities.helpful_functions import n_word_struct
from .utils import ReportDir

MEM_MAP_SUBDIR_NAME = "memory_map_reports"
MEM_MAP_FILENAME = "memory_map_from_processor_{0:d}_{1:d}_{2:d}.txt"
REGION_HEADER_SIZE = 2 * BYTES_PER_WORD


class MemoryMapOnHostChipReport(object):
    """ Report on memory usage. Creates a report that states where in SDRAM \
        each region is (read from machine)
    """

    def __call__(self, report_default_directory, dsg_targets, transceiver):
        """
        :param str report_default_directory:
            the folder where reports are written
        :param dict(tuple(int,int,int),...) dsg_targets:
            the map between placement and file writer
        :param ~spinnman.transceiver.Transceiver transceiver:
            the spinnMan instance
        """
        rpt_dir = ReportDir(report_default_directory, MEM_MAP_SUBDIR_NAME)
        progress = ProgressBar(dsg_targets, "Writing memory map reports")
        for (x, y, p) in progress.over(dsg_targets):
            with rpt_dir.file(MEM_MAP_FILENAME.format(x, y, p)) as f:
                self._describe_mem_map(f, transceiver, x, y, p)

    def _describe_mem_map(self, f, txrx, x, y, p):
        """
        :param ~io.TextIOBase f:
        :param ~spinnman.transceiver.Transceiver txrx:
        """
        # pylint: disable=too-many-arguments
        # Read the memory map data from the given core
        region_table_addr = self._get_region_table_addr(txrx, x, y, p)
        memmap_data = n_word_struct(MAX_MEM_REGIONS).unpack(txrx.read_memory(
            x, y, region_table_addr, BYTES_PER_WORD * MAX_MEM_REGIONS))

        # Convert the map to a human-readable description
        f.write("On chip data specification executor\n\n")
        for i, region_address in enumerate(memmap_data):
            f.write(
                f"Region {i:d}:\n\tstart address: 0x{region_address:x}\n\n")

    @staticmethod
    def _get_region_table_addr(txrx, x, y, p):
        """
        :param ~spinnman.transceiver.Transceiver txrx:
        """
        user_0_addr = txrx.get_user_0_register_address_from_core(p)
        return txrx.read_word(x, y, user_0_addr) + REGION_HEADER_SIZE
