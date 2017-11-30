from spinn_utilities.progress_bar import ProgressBar
from data_specification.constants import MAX_MEM_REGIONS
from spinn_front_end_common.utilities.exceptions import ConfigurationException

import logging
import os
import struct

logger = logging.getLogger(__name__)
_ONE_WORD = struct.Struct("<I")
MEM_MAP_SUBDIR_NAME = "memory_map_reports"
MEM_MAP_FILENAME = "memory_map_from_processor_{0:d}_{1:d}_{2:d}.txt"


class MemoryMapOnHostChipReport(object):
    """ Report on memory usage
    """

    def __call__(
            self, report_default_directory, dsg_targets, transceiver,
            loaded_app_data_token):
        """ creates a report that states where in SDRAM each region is \
        (read from machine)

        :param report_default_directory: the folder where reports are written
        :param dsg_targets: the map between placement and file writer
        :param transceiver: the spinnMan instance
        :param loaded_app_data_token: flag that app data has been loaded
        :rtype: None
        """

        if not loaded_app_data_token:
            raise ConfigurationException(
                "Needs to have loaded app data for this to work.")

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
                logger.error("Generate_placement_reports: Can't open file"
                             " {} for writing.".format(file_name))

    def _describe_mem_map(self, f, txrx, x, y, p):
        # Read the memory map data from the given core
        user_0_addr = txrx.get_user_0_register_address_from_core(x, y, p)
        pointer_table_addr = self._get_app_pointer_table(
            txrx, x, y, user_0_addr)
        memmap_data = buffer(txrx.read_memory(
            x, y, pointer_table_addr, 4 * MAX_MEM_REGIONS))

        # Convert the map to a human-readable description
        f.write("On chip data specification executor\n\n")
        for i in xrange(MAX_MEM_REGIONS):
            region_address = int(_ONE_WORD.unpack_from(
                memmap_data, i * 4)[0])
            f.write("Region {0:d}:\n\t start address: 0x{1:x}\n\n"
                    .format(i, region_address))

    def _get_app_pointer_table(self, txrx, x, y, table_pointer):
        encoded_address = buffer(txrx.read_memory(x, y, table_pointer, 4))
        return int(_ONE_WORD.unpack_from(encoded_address)[0]) + 8
