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

import logging
import os
import sys
from collections import defaultdict
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.interface.interface_functions.\
    machine_bit_field_router_compressor import (
        PROV_TOP_NAME)
from spinn_front_end_common.utilities.helpful_functions import (
    find_executable_start_type)
from spinn_front_end_common.utilities.report_functions.\
    bit_field_summary import (
        BitFieldSummary)
from spinn_front_end_common.utilities.utility_objs import ExecutableType

logger = FormatAdapter(logging.getLogger(__name__))
_FILE_NAME = "bit_field_compressed_summary.rpt"


class BitFieldCompressorReport(object):
    """ Generates a report that shows the impact of the compression of \
        bitfields into the routing table.
    """
    def __call__(
            self, report_default_directory, machine_graph, placements,
            provenance_items=None, retry_count=None):
        """
        :param str report_default_directory: report folder
        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
            the machine graph
        :param ~pacman.model.placements.Placements placements: the placements
        :param provenance_items: prov items
        :type provenance_items: list(ProvenanceDataItem) or None
        :param retry_count:
            Number of times that the sorters should set of the compressions
            again. None for as much as needed
        :type retry_count: int or None
        :return: a summary, or `None` if the report file can't be written
        :rtype: BitFieldSummary
        """
        if provenance_items is None:
            provenance_items = []
        file_name = os.path.join(report_default_directory, _FILE_NAME)
        try:
            with open(file_name, "w") as f:
                return self._write_report(
                    f, provenance_items, machine_graph, placements,
                    retry_count)
        except IOError:
            logger.exception("Generate_placement_reports: Can't open file"
                             " {} for writing.", _FILE_NAME)
            return None

    @staticmethod
    def _merged_component(provenance_items, writer, to_merge_per_chip):
        """ Report how many bitfields were merged into the router.

        :param list(ProvenanceDataItem) provenance_items: prov items
        :param ~io.FileIO writer: file writer.
        :param dict((int,int): int) to_merge_per_chip:
            number of bitfields per chip
        :return: tuple containing 4 elements.
         1. min_bit_fields merged in a chip,
         2. the max bit_fields merged in a chip,
         3. the total bit_fields_merged into all the routers.
         4. average number of bit-fields merged on the routers.
        :rtype: tuple(int or str, int or str, int or str, float or str)
        """
        top_bit_field = 0
        min_bit_field = sys.maxsize
        total_bit_fields_merged = 0
        average_per_chip_merged = 0
        n_chips = 0
        to_merge_chips = set(to_merge_per_chip.keys())

        found = False
        for prov_item in provenance_items:
            if prov_item.names[0] == PROV_TOP_NAME:
                bits = prov_item.names[1].split("_")
                x = int(bits[3])
                y = int(bits[4])
                if (x, y) in to_merge_per_chip:
                    to_merge = to_merge_per_chip[(x, y)]
                    found = True
                    to_merge_chips.remove((x, y))
                    writer.write(
                        "Chip {}:{} has {} bitfields out of {} merged into it"
                        "\n".format(x, y, prov_item.value, to_merge))
                    total_bit_fields_merged += int(prov_item.value)
                    if int(prov_item.value) > top_bit_field:
                        top_bit_field = int(prov_item.value)
                    if int(prov_item.value) < min_bit_field:
                        min_bit_field = int(prov_item.value)
                    average_per_chip_merged += int(prov_item.value)
                    n_chips += 1

        if found:
            average_per_chip_merged = \
                float(average_per_chip_merged) / float(n_chips)
        else:
            min_bit_field = "N/A"
            top_bit_field = "N/A"
            total_bit_fields_merged = "N/A"
            average_per_chip_merged = "N/A"

        if len(to_merge_chips) > 0:
            writer.write(
                "The Chips {} had bitfields. \n"
                "But no record was found of any attepmt to merge them \n"
                "".format(to_merge_chips))

        return (min_bit_field, top_bit_field, total_bit_fields_merged,
                average_per_chip_merged)

    @staticmethod
    def _before_merge_component(machine_graph, placements):
        """
        :param ~.MachineGraph machine_graph:
        :param ~.Placements placements:
        :rtype: tuple(int, int, int, float or int)
        """
        total_to_merge = 0
        to_merge_per_chip = defaultdict(int)

        for placement in placements:
            binary_start_type = find_executable_start_type(placement.vertex)

            if binary_start_type != ExecutableType.SYSTEM:
                seen_partitions = set()
                for incoming_partition in machine_graph.\
                        get_multicast_edge_partitions_ending_at_vertex(
                            placement.vertex):
                    if incoming_partition not in seen_partitions:
                        total_to_merge += 1
                        to_merge_per_chip[placement.x, placement.y] += 1
                        seen_partitions.add(incoming_partition)

        max_bit_fields_on_chip = 0
        min_bit_fields_on_chip = sys.maxsize

        for bitfield_count in to_merge_per_chip.values():
            if bitfield_count > max_bit_fields_on_chip:
                max_bit_fields_on_chip = bitfield_count
            if bitfield_count < min_bit_fields_on_chip:
                min_bit_fields_on_chip = bitfield_count

        if len(to_merge_per_chip) == 0:
            average = 0
        else:
            average = float(total_to_merge) / float(len(to_merge_per_chip))

        return (total_to_merge, max_bit_fields_on_chip,
                min_bit_fields_on_chip, average, to_merge_per_chip)

    def _rety_warning(self, writer,  retry_count):
        if retry_count is None:
            return
        # Wet finger estimates with no proof they are right
        if retry_count < 5:
            margin = "10%"
        elif retry_count < 15:
            margin = "5%"
        elif retry_count < 30:
            margin = "2%"
        else:
            margin = "1%"
        writer.write(
            "\n\nWarning the number of retires was capped at {}. "
            "\nWithout this cap the bitfileds merges is likely to be higher. "
            "\nA very crude estimate suggests up to {} better."
            "\nRemoving router_table_compression_with_bit_field_retry_count "
            "from your cfg file may improve bitfields merged.".format(
                retry_count, margin))

    def _write_report(
            self, writer, provenance_items, machine_graph, placements,
            retry_count):
        """ writes the report

        :param ~io.FileIO writer: the file writer
        :param list(ProvenanceDataItem) provenance_items: the prov items
        :param ~.MachineGraph machine_graph: the machine graph
        :param ~.Placements placements: the placements
        :param retry_count:
            Number of times that the sorters should set of the compressions
            again. None for as much as needed
        :type retry_count: int or None
        :return: a summary
        :rtype: BitFieldSummary
        """

        (total_to_merge, max_to_merge_per_chip, low_to_merge_per_chip,
         average_per_chip_to_merge, to_merge_per_chip) = \
            self._before_merge_component(machine_graph, placements)
        (min_bit_field, top_bit_field, total_bit_fields_merged,
         average_per_chip_merged) = self._merged_component(
            provenance_items, writer, to_merge_per_chip)

        writer.write(
            "\n\nSummary: merged total {} out of {} bitfields. best per chip "
            "was {} and the most on one chip was {}. worst"
            " per chip was {} where the least on a chip was {}. average over "
            "all chips is {} out of {}".format(
                total_bit_fields_merged, total_to_merge, top_bit_field,
                max_to_merge_per_chip, min_bit_field, low_to_merge_per_chip,
                average_per_chip_merged, average_per_chip_to_merge))

        self._rety_warning(writer, retry_count)

        return BitFieldSummary(
            lowest_per_chip=min_bit_field, max_per_chip=top_bit_field,
            total_merged=total_bit_fields_merged,
            total_to_merge=total_to_merge,
            max_to_merge_per_chip=max_to_merge_per_chip,
            low_to_merge_per_chip=low_to_merge_per_chip,
            average_per_chip_merged=average_per_chip_merged,
            average_per_chip_to_merge=average_per_chip_to_merge)
