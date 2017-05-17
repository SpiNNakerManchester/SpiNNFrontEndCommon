from spinn_utilities.progress_bar import ProgressBar
from data_specification import constants
from spinn_front_end_common.utilities import exceptions

import logging
import os
import struct

logger = logging.getLogger(__name__)

MEM_MAP_SUBDIR_NAME = "memory_map_reports"


class FrontEndCommonMemoryMapOnHostChipReport(object):
    """ Report on memory usage
    """

    def __call__(
            self, report_default_directory, dsg_targets, transceiver,
            loaded_app_data_token):
        """ creates a report that states where in sdram each region is
        (read from machine)

        :param report_default_directory: the folder where reports are written
        :param dsg_targets: the map between placement and file writer
        :param transceiver: the spinnMan instance
        :param loaded_app_data_token: flag that app data has been loaded
        :return: None
        """

        if not loaded_app_data_token:
            raise exceptions.ConfigurationException(
                "Needs to have loaded app data for this to work.")

        directory_name = os.path.join(
            report_default_directory, MEM_MAP_SUBDIR_NAME)
        if not os.path.exists(directory_name):
            os.makedirs(directory_name)

        progress = ProgressBar(dsg_targets, "Writing memory map reports")
        for (x, y, p) in progress.over(dsg_targets):
            file_name = os.path.join(
                directory_name,
                "memory_map_from_processor"
                "_{0:d}_{1:d}_{2:d}.txt".format(x, y, p))
            try:
                with open(file_name, "w") as f:
                    f.write("On chip data specification executor\n\n")

                    dsg_app_pointer_table_address_pointer = transceiver.\
                        get_user_0_register_address_from_core(x, y, p)

                    dsg_app_pointer_table_address = \
                        self._get_app_pointer_table(
                            transceiver, x, y,
                            dsg_app_pointer_table_address_pointer)

                    report_bytes = 4 * constants.MAX_MEM_REGIONS

                    mem_map_report_data = buffer(transceiver.read_memory(
                        x, y, dsg_app_pointer_table_address, report_bytes))

                    offset = 0
                    for i in xrange(constants.MAX_MEM_REGIONS):
                        region_address = int(struct.unpack_from(
                            "<I", mem_map_report_data, offset)[0])
                        offset += 4
                        f.write("Region {0:d}:\n\t start address: 0x{1:x}\n\t"
                                .format(i, region_address))
            except IOError:
                logger.error("Generate_placement_reports: Can't open file"
                             " {} for writing.".format(file_name))

    def _get_app_pointer_table(self, txrx, x, y, table_pointer):
        encoded_address = buffer(txrx.read_memory(x, y, table_pointer, 4))
        return int(struct.unpack_from("<I", encoded_address)[0]) + 8
