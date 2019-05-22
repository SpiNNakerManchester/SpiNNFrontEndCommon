import logging
import os

import sys

from spinn_front_end_common.interface.interface_functions.\
    machine_bit_field_router_compressor import PROV_TOP_NAME
from spinn_front_end_common.utilities.report_functions.bit_field_summary import \
    BitFieldSummary
from spinn_utilities.log import FormatAdapter

logger = FormatAdapter(logging.getLogger(__name__))

_FILE_NAME = "bit_field_summary.rpt"


class BitFieldCompressorReport(object):

    def __call__(self, report_default_directory, provenance_items):
        file_name = os.path.join(report_default_directory, _FILE_NAME)

        try:
            with open(file_name, "w") as f:
                return self._write_report(f, provenance_items)
        except IOError:
            logger.exception("Generate_placement_reports: Can't open file"
                             " {} for writing.", _FILE_NAME)

    @staticmethod
    def _write_report(writer, provenance_items):
        top_bit_field = 0
        min_bit_field = sys.maxint
        total_bit_fields_merged = 0

        for prov_item in provenance_items:
            if prov_item.names[0] == PROV_TOP_NAME:
                bits = prov_item.names[1].split("_")
                writer.write(
                    "Chip {}:{} has {} bitfields merged into it\n".format(
                        bits[0], bits[1], prov_item.value))
                total_bit_fields_merged += int(prov_item.value)
                if int(prov_item.value) > top_bit_field:
                    top_bit_field = int(prov_item.value)
                if int(prov_item.value) < min_bit_field:
                    min_bit_field = int(prov_item.value)

        writer.write(
            "\n\nSummary: merged total {} bitfields, best per chip was {} worst"
            " per chip was {}".format(
                total_bit_fields_merged, top_bit_field, min_bit_field))

        return BitFieldSummary(
            lowest_per_chip=min_bit_field, max_per_chip=top_bit_field,
            total_merged=total_bit_fields_merged)


