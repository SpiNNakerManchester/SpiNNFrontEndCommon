from data_specification import constants

from spinn_machine.utilities.progress_bar import ProgressBar

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

        progress_bar = ProgressBar(len(dsg_targets),
                                   "Writing memory map reports")
        for (x, y, p) in dsg_targets:

            file_name = os.path.join(
                directory_name,
                "memory_map_from_processor"
                "_{0:d}_{1:d}_{2:d}.txt".format(x, y, p))
            output = None
            try:
                output = open(file_name, "w")
            except IOError:
                logger.error("Generate_placement_reports: Can't open file"
                             " {} for writing.".format(file_name))

            output.write("On chip data specification executor\n\n")

            dsg_app_pointer_table_address_pointer = transceiver.\
                get_user_0_register_address_from_core(x, y, p)

            report_data_address_encoded = buffer(transceiver.read_memory(
                x, y, dsg_app_pointer_table_address_pointer, 4))

            dsg_app_pointer_table_address = struct.unpack_from(
                "<I", report_data_address_encoded)[0] + 8

            report_bytes = 4 * constants.MAX_MEM_REGIONS

            mem_map_report_data = buffer(transceiver.read_memory(
                x, y, dsg_app_pointer_table_address, report_bytes))

            offset = 0
            for i in xrange(constants.MAX_MEM_REGIONS):
                region_address = int(struct.unpack_from(
                    "<I", mem_map_report_data, offset)[0])
                offset += 4
                output.write("Region {0:d}:\n\t start address: 0x{1:x}\n\t"
                             .format(i, region_address))

            output.flush()
            output.close()
            progress_bar.update()
        progress_bar.end()
