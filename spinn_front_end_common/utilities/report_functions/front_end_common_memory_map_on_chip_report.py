from data_specification import constants
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.utilities import exceptions

import logging
import os
import struct

logger = logging.getLogger(__name__)

MEM_MAP_SUBDIR_NAME = "memory_map_reports"


class FrontEndCommonMemoryMapOnChipReport(object):
    """ Report on memory usage
    """

    def __call__(
            self, report_default_directory, dsg_targets, transceiver,
            loaded_app_data_token):
        """ creates a report that states where in sdram each region is

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
            with open(file_name, "w") as output:
                self._write_processor_memory_map(output, transceiver, x, y, p)

    def _write_processor_memory_map(self, output, txrx, x, y, p):
        output.write("On chip data specification executor\n\n")

        report_data_address = self._get_report_data_address(txrx, x, y, p)
        report_bytes = \
            _MemoryChannelState.STRUCT_SIZE * constants.MAX_MEM_REGIONS

        mem_map_report_data = buffer(txrx.read_memory(
            x, y, report_data_address, report_bytes))

        offset = 0
        for i in xrange(constants.MAX_MEM_REGIONS):
            region = _MemoryChannelState.from_bytestring(
                mem_map_report_data, offset)
            offset += _MemoryChannelState.STRUCT_SIZE

            if region.start_address == 0:
                output.write("Region {0:d}: Unused\n\n".format(i))
                continue

            output.write(
                "Region {0:d}:\n\t"
                "start address: 0x{1:x}\n\t"
                "size: {2:d}\n\t"
                "unfilled: {3:s}\n\t"
                "write pointer: 0x{4:x}\n\t"
                "size currently written(based on the "
                "write pointer): {5:d}\n\n".format(
                    i, region.start_address, region.size,
                    region.unfilled_tf, region.write_pointer,
                    0 if region.unfilled else region.written))

    @staticmethod
    def _get_report_data_address(txrx, x, y, p):
        data_address_pointer = txrx.get_user_1_register_address_from_core(
            x, y, p)
        data_address_encoded = txrx.read_memory(
            x, y, data_address_pointer, 4)
        return struct.unpack_from("<I", buffer(data_address_encoded))[0]


class _MemoryChannelState(object):
    # 4 fields each of 4 bytes
    STRUCT_SIZE = 16

    def __init__(self, start_address, size, unfilled, write_pointer):
        self._start_address = start_address
        self._size = size
        self._unfilled = unfilled
        self._write_pointer = write_pointer

    @property
    def start_address(self):
        return self._start_address

    @property
    def size(self):
        return self._size

    @property
    def unfilled(self):
        return self._unfilled

    @property
    def unfilled_tf(self):
        return "True" if self._unfilled else "False"

    @property
    def write_pointer(self):
        return self._write_pointer

    @property
    def written(self):
        return self._write_pointer - self._start_address

    @staticmethod
    def from_bytestring(data, offset=0):
        start, size, unfilled, write = \
            struct.unpack_from("<IIII", data, offset)
        return _MemoryChannelState(start, size, unfilled, write)

    def bytestring(self):
        return struct.pack("<IIII", self._start_address, self._size,
                           self._unfilled, self._write_pointer)
