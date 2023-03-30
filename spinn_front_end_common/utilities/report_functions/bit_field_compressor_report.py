# Copyright (c) 2019 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
import sys
from collections import defaultdict
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.provenance import (
    ProvenanceReader, ProvenanceWriter)
from .bit_field_summary import BitFieldSummary
from spinn_front_end_common.utilities.utility_objs import ExecutableType

logger = FormatAdapter(logging.getLogger(__name__))
_FILE_NAME = "bit_field_compressed_summary.rpt"
# provenance data item names

MERGED_NAME = "bit_fields_merged"
NOT_APPLICABLE = "N/A"


def generate_provenance_item(x, y, bit_fields_merged):
    """
    Generates a provenance item in the format BitFieldCompressorReport expects.

    :param x:
    :param y:
    :param bit_fields_merged:
    """
    with ProvenanceWriter() as db:
        db.insert_router(x, y, MERGED_NAME, bit_fields_merged)


def bitfield_compressor_report():
    """
    Generates a report that shows the impact of the compression of
    bitfields into the routing table.

    :return: a summary, or `None` if the report file can't be written
    :rtype: BitFieldSummary
    """
    file_name = os.path.join(FecDataView.get_run_dir_path(), _FILE_NAME)
    try:
        with open(file_name, "w", encoding="utf-8") as f:
            _write_report(f)
    except IOError:
        logger.exception("Generate_placement_reports: Can't open file"
                         " {} for writing.", _FILE_NAME)


def _merged_component(to_merge_per_chip, writer):
    """
    Report how many bitfields were merged into the router.

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
    with ProvenanceReader() as db:
        for (x, y, merged) in db.get_router_by_chip(
                MERGED_NAME):
            if (x, y) not in to_merge_per_chip:
                continue
            to_merge = to_merge_per_chip[x, y]
            to_merge_chips.discard((x, y))
            found = True
            writer.write(
                f"Chip {x}:{y} has {merged} bitfields out of {to_merge} "
                f"merged into it. Which is {merged / to_merge:.2%}\n")
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
            f"The Chips {to_merge_chips} had bitfields.\n"
            "But no record was found of any attempt to merge them.\n")

    return (min_bit_field, top_bit_field, total_bit_fields_merged,
            average_per_chip_merged)


def _compute_to_merge_per_chip():
    """
    :rtype: tuple(int, int, int, float or int)
    """
    total_to_merge = 0
    to_merge_per_chip = defaultdict(int)

    for partition in FecDataView.iterate_partitions():
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
    """
    Writes the report.

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
        f"\n\nBefore merge there where {total_to_merge} bitfields on "
        f"{len(to_merge_per_chip)} Chips ranging from {max_to_merge_per_chip} "
        f"to {low_to_merge_per_chip} bitfields per chip with an average "
        f"of {average_per_chip_to_merge}")
    writer.write(
        f"\nSuccessfully merged {total_bit_fields_merged} bitfields ranging "
        f"from {top_bit_field} to {min_bit_field} bitfields per chip with an "
        f"average of {average_per_chip_merged}")
    if total_to_merge:
        if total_bit_fields_merged == NOT_APPLICABLE:
            writer.write(f"\nNone of the {total_to_merge} bitfields merged")
        else:
            writer.write("\nIn total {:.2%} of the bitfields merged".format(
                total_bit_fields_merged / total_to_merge))

    return BitFieldSummary(
        lowest_per_chip=min_bit_field, max_per_chip=top_bit_field,
        total_merged=total_bit_fields_merged,
        total_to_merge=total_to_merge,
        max_to_merge_per_chip=max_to_merge_per_chip,
        low_to_merge_per_chip=low_to_merge_per_chip,
        average_per_chip_merged=average_per_chip_merged,
        average_per_chip_to_merge=average_per_chip_to_merge)
