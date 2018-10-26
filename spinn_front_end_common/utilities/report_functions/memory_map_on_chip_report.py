from data_specification.constants import MAX_MEM_REGIONS
from spinn_utilities.progress_bar import ProgressBar

import logging
import os
import struct

logger = logging.getLogger(__name__)
_ONE_WORD = struct.Struct("<I")
_FOUR_WORDS = struct.Struct("<IIII")
MEM_MAP_SUBDIR_NAME = "memory_map_reports"
MEM_MAP_FILENAME = "memory_map_from_processor_{0:d}_{1:d}_{2:d}.txt"


class MemoryMapOnChipReport(object):
    """ Report on memory usage.
    """

    def __call__(self, report_default_directory, dsg_targets, transceiver):
        """ Creates a report that states where in SDRAM each region is

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
            with open(file_name, "w") as f:
                self._write_processor_memory_map(f, transceiver, x, y, p)

    def _write_processor_memory_map(self, f, txrx, x, y, p):
        # pylint: disable=too-many-arguments
        f.write("On chip data specification executor\n\n")

        report_data_address = self._get_report_data_address(txrx, x, y, p)
        report_bytes = _MemoryChannelState.STRUCT_SIZE * MAX_MEM_REGIONS

        report_data = txrx.read_memory(x, y, report_data_address, report_bytes)

        for i in range(MAX_MEM_REGIONS):
            region = _MemoryChannelState.from_bytestring(
                report_data, i * _MemoryChannelState.STRUCT_SIZE)
            self._describe_region(f, region, i)
            f.write("\n\n")

    @staticmethod
    def _describe_region(f, region, index):
        f.write("Region {0:d}:".format(index))
        if region.start_address == 0:
            f.write(" Unused")
        else:
            f.write(
                "\n\tstart address: 0x{0:x}"
                "\n\tsize: {1:d}"
                "\n\tunfilled: {2:s}"
                "\n\twrite pointer: 0x{3:x}\n\t"
                "size currently written (based on the write pointer): {4:d}"
                .format(
                    region.start_address, region.size,
                    region.unfilled_tf, region.write_pointer,
                    0 if region.unfilled else region.written))

    @staticmethod
    def _get_report_data_address(txrx, x, y, p):
        data_address_pointer = txrx.get_user_1_register_address_from_core(p)
        data_address_encoded = txrx.read_memory(
            x, y, data_address_pointer, 4)
        return _ONE_WORD.unpack_from(data_address_encoded)[0]


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
        start, size, unfilled, write = _FOUR_WORDS.unpack_from(data, offset)
        return _MemoryChannelState(start, size, unfilled, write)

    def bytestring(self):
        return _FOUR_WORDS.pack(self._start_address, self._size,
                                self._unfilled, self._write_pointer)
