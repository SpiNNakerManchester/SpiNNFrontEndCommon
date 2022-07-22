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
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.provenance import ProvenanceWriter
from .bit_field_summary import BitFieldSummary
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.interface.provenance import ProvenanceReader

logger = FormatAdapter(logging.getLogger(__name__))
_FILE_NAME = "bit_field_compressed_summary.rpt"
# provenance data item names

MERGED_NAME = "bit_fields_merged"
NOT_APPLICABLE = "N/A"


def generate_provenance_item(x, y, bit_fields_merged):
    """
    Generates a provenance item in the format BitFieldCompressorReport expects
    :param x:
    :param y:
    :param bit_fields_merged:
    :return:
    """
    with ProvenanceWriter() as db:
        db.insert_router(x, y, MERGED_NAME, bit_fields_merged)


def bitfield_compressor_report():
    """
    Generates a report that shows the impact of the compression of \
    bitfields into the routing table.

    :return: a summary, or `None` if the report file can't be written
    :rtype: BitFieldSummary
    """
    file_name = os.path.join(FecDataView.get_run_dir_path(), _FILE_NAME)
    try:
        with open(file_name, "w", encoding="utf-8") as f:
            return _write_report(f)
    except IOError:
        logger.exception("Generate_placement_reports: Can't open file"
                         " {} for writing.", _FILE_NAME)
        return None


def _merged_component(to_merge_per_chip, writer):
    """ Report how many bitfields were merged into the router.

    :param dict([int, int], int: to_merge_per_chip: number of bitfields
        that could be merged per chip
    :param ~io.FileIO writer: file writer.
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
    for (x, y, merged) in ProvenanceReader().get_router_by_chip(
            MERGED_NAME):
        if (x, y) not in to_merge_per_chip:
            continue
        to_merge = to_merge_per_chip[x, y]
        to_merge_chips.discard((x, y))
        found = True
        writer.write(
            "Chip {}:{} has {} bitfields out of {} merged into it."
            " Which is {:.2%}\n".format(
                x, y, merged, to_merge, merged / to_merge))
        total_bit_fields_merged += int(merged)
        if merged > top_bit_field:
            top_bit_field = merged
        if merged < min_bit_field:
            min_bit_field = merged
        average_per_chip_merged += merged
        n_chips += 1

    if found:
        average_per_chip_merged = (
            float(average_per_chip_merged) / float(n_chips))
    else:
        min_bit_field = NOT_APPLICABLE
        top_bit_field = NOT_APPLICABLE
        total_bit_fields_merged = NOT_APPLICABLE
        average_per_chip_merged = NOT_APPLICABLE

    if len(to_merge_chips) > 0:
        writer.write(
            "The Chips {} had bitfields. \n"
            "But no record was found of any attepmt to merge them \n"
            "".format(to_merge_chips))

    return (min_bit_field, top_bit_field, total_bit_fields_merged,
            average_per_chip_merged)


def _compute_to_merge_per_chip():
    """
    :rtype: tuple(int, int, int, float or int)
    """
    total_to_merge = 0
    to_merge_per_chip = defaultdict(int)

    app_graph = FecDataView.get_runtime_graph()
    for partition in app_graph.outgoing_edge_partitions:
        for edge in partition.edges:
            splitter = edge.post_vertex.splitter
            for vertex in splitter.get_source_specific_in_coming_vertices(
                    partition.pre_vertex, partition.identifier):
                if not isinstance(vertex, AbstractHasAssociatedBinary):
                    continue
                if vertex.get_binary_start_type() == ExecutableType.SYSTEM:
                    continue
                place = FecDataView.get_placement_of_vertex(vertex)
                to_merge_per_chip[place.chip] += 1
                total_to_merge += 1

    return total_to_merge, to_merge_per_chip


def _before_merge_component(total_to_merge, to_merge_per_chip):
    """
    :rtype: tuple(int, int, int, float or int)
    """
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

    return max_bit_fields_on_chip, min_bit_fields_on_chip, average


def _write_report(writer):
    """ writes the report

    :param ~io.FileIO writer: the file writer
    :return: a summary
    :rtype: BitFieldSummary
    """
    total_to_merge, to_merge_per_chip = _compute_to_merge_per_chip()
    (max_to_merge_per_chip, low_to_merge_per_chip,
     average_per_chip_to_merge) = _before_merge_component(
        total_to_merge, to_merge_per_chip)
    (min_bit_field, top_bit_field, total_bit_fields_merged,
     average_per_chip_merged) = _merged_component(to_merge_per_chip, writer)
    writer.write(
        "\n\nBefore merge there where {} bitfields on {} Chips "
        "ranging from {} to {} bitfields per chip with an average of {}"
        "".format(
            total_to_merge, len(to_merge_per_chip), max_to_merge_per_chip,
            low_to_merge_per_chip, average_per_chip_to_merge))
    writer.write(
        "\nSuccessfully merged {} bitfields ranging from {} to {} "
        "bitfields per chip with an average of {}".format(
            total_bit_fields_merged, top_bit_field, min_bit_field,
            average_per_chip_merged))
    if total_to_merge:
        if total_bit_fields_merged == NOT_APPLICABLE:
            writer.write(
                "\nNone of the {} bitfields merged".format(
                    total_to_merge))
        else:
            writer.write(
                "\nIn total {:.2%} of the bitfields merged".format(
                    total_bit_fields_merged / total_to_merge))

    return BitFieldSummary(
        lowest_per_chip=min_bit_field, max_per_chip=top_bit_field,
        total_merged=total_bit_fields_merged,
        total_to_merge=total_to_merge,
        max_to_merge_per_chip=max_to_merge_per_chip,
        low_to_merge_per_chip=low_to_merge_per_chip,
        average_per_chip_merged=average_per_chip_merged,
        average_per_chip_to_merge=average_per_chip_to_merge)
