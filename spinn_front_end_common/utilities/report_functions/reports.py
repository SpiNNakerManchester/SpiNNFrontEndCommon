# Copyright (c) 2017 The University of Manchester
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
import time
from typing import Iterable, Optional, TextIO, Tuple

from spinn_utilities.config_holder import get_report_path
from spinn_utilities.ordered_set import OrderedSet
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter

from spinn_machine import Chip, MulticastRoutingEntry, Router

from pacman.model.graphs.application import (
    ApplicationEdgePartition, ApplicationVertex)
from pacman.model.graphs.machine import (
    MachineFPGAVertex, MachineSpiNNakerLinkVertex, MachineVertex)
from pacman.model.routing_tables import (
    AbstractMulticastRoutingTable, MulticastRoutingTables)
from pacman.model.routing_info import BaseKeyAndMask, RoutingInfo
from pacman.utilities.algorithm_utilities.routing_algorithm_utilities import (
    get_app_partitions)
from pacman.utilities.algorithm_utilities.routes_format import format_route

from spinn_front_end_common.data import FecDataView
from .router_summary import RouterSummary

logger = FormatAdapter(logging.getLogger(__name__))

_LINK_LABELS = {0: 'E', 1: 'NE', 2: 'N', 3: 'W', 4: 'SW', 5: 'S'}

_LOWER_16_BITS = 0xFFFF


def tag_allocator_report() -> None:
    """
    Reports the tags that are being used by the tool chain for this
    simulation.
    """
    tag_infos = FecDataView.get_tags()
    file_name = get_report_path("path_tag_allocation_reports_host")
    try:
        with open(file_name, "w", encoding="utf-8") as f:
            progress = ProgressBar(
                len(list(tag_infos.ip_tags)) +
                len(list(tag_infos.reverse_ip_tags)),
                "Reporting Tags")
            for ip_tag in progress.over(tag_infos.ip_tags, False):
                f.write(str(ip_tag) + "\n")
            for reverse_ip_tag in progress.over(tag_infos.reverse_ip_tags):
                f.write(str(reverse_ip_tag) + "\n")
    except IOError:
        logger.error(
            "Generate tag report: Can't open file {} for writing.", file_name)


def placer_reports_with_application_graph() -> None:
    """
    Reports that can be produced from placement given a application
    graph's existence.
    """
    placement_report_with_application_graph_by_vertex()
    placement_report_with_application_graph_by_core()


def router_summary_report() -> Optional[RouterSummary]:
    """
    Generates a text file of routing summaries.
    """
    file_name = get_report_path("path_router_summary_report")
    progress = ProgressBar(FecDataView.get_machine().n_chips,
                           "Generating Routing summary report")
    routing_tables = FecDataView.get_uncompressed()
    return _do_router_summary_report(file_name, progress, routing_tables)


def router_compressed_summary_report(
        routing_tables: MulticastRoutingTables) -> Optional[RouterSummary]:
    """
    Generates a text file of routing summaries.

    :param routing_tables: The in-operation COMPRESSED routing tables.
    """
    file_name = get_report_path("path_compression_summary")
    progress = ProgressBar(FecDataView.get_machine().n_chips,
                           "Generating Routing summary report")
    return _do_router_summary_report(file_name, progress, routing_tables)


def _do_router_summary_report(
        file_name: str, progress: ProgressBar,
        routing_tables: MulticastRoutingTables) -> Optional[RouterSummary]:
    """
    :param file_name:
    :param progress:
    :param routing_tables:
        The compressed or uncompressed tables being reported
    :return: RouterSummary
    """
    time_date_string = time.strftime("%c")
    convert = Router.convert_routing_table_entry_to_spinnaker_route
    try:
        with open(file_name, "w", encoding="utf-8") as f:
            f.write("        Routing Summary Report\n")
            f.write("        ======================\n\n")
            f.write(f"Generated: {time_date_string} "
                    f"for target machine '{FecDataView.get_ipaddress()}'\n\n")

            total_entries = 0
            max_entries = 0
            max_none_defaultable = 0
            max_link_only = 0
            max_spinnaker_routes = 0
            for (x, y) in progress.over(
                    FecDataView.get_machine().chip_coordinates):
                table = routing_tables.get_routing_table_for_chip(x, y)
                if table is not None:
                    entries = table.number_of_entries
                    defaultable = table.number_of_defaultable_entries
                    link_only = 0
                    spinnaker_routes = set()
                    for entry in table.multicast_routing_entries:
                        if not entry.processor_ids:
                            link_only += 1
                        spinnaker_routes.add(convert(entry))
                    f.write(
                        f"Chip {x}:{y} has {entries} entries of which "
                        f"{defaultable} are defaultable and {link_only} link "
                        f"only with {len(spinnaker_routes)} unique spinnaker "
                        "routes\n")
                    total_entries += entries
                    max_entries = max(max_entries, entries)
                    max_none_defaultable = max(
                        max_none_defaultable, entries - defaultable)
                    max_link_only = max(max_link_only, link_only)
                    max_spinnaker_routes = max(
                        max_spinnaker_routes, len(spinnaker_routes))

            f.write(
                f"\nTotal entries {total_entries}, max per chip {max_entries} "
                f"max non-defaultable {max_none_defaultable} "
                f"max link only {max_link_only} "
                f"max unique spinnaker routes {max_spinnaker_routes}\n\n")
            return RouterSummary(
                total_entries, max_entries, max_none_defaultable,
                max_link_only, max_spinnaker_routes)

    except IOError:
        logger.exception(
            "Generate routing summary report: Can't open file {} for writing.",
            file_name)
        return None


def router_report_from_paths() -> None:
    """
    Generates a text file of routing paths.
    """
    file_name = get_report_path("path_router_reports")
    time_date_string = time.strftime("%c")
    partitions = get_app_partitions()
    try:
        with open(file_name, "w", encoding="utf-8") as f:
            progress = ProgressBar(len(partitions),
                                   "Generating Routing path report")

            f.write("        Edge Routing Report\n")
            f.write("        ===================\n\n")
            f.write(f"Generated: {time_date_string} "
                    f"for target machine '{FecDataView.get_ipaddress()}'\n\n")

            for partition in progress.over(partitions):
                _write_one_router_partition_report(f, partition)
    except IOError:
        logger.exception(
            "Generate routing reports: Can't open file {} for writing.",
            file_name)


def _write_one_router_partition_report(
        f: TextIO, partition: ApplicationEdgePartition) -> None:
    source = partition.pre_vertex
    outgoing = source.splitter.get_out_going_vertices(partition.identifier)
    f.write(f"Source Application vertex {source}, partition"
            f" {partition.identifier}\n")

    routing_infos = FecDataView.get_routing_infos()
    for edge in partition.edges:
        for m_vertex in outgoing:
            r_info = routing_infos.get_info_from(
                m_vertex, partition.identifier)
            path = _search_route(m_vertex, r_info.key_and_mask)
            f.write(
                f"    Edge '{edge.label}', "
                f"from vertex: '{edge.pre_vertex.label}' "
                f"to vertex: '{edge.post_vertex.label}'{path}\n")

            # End one entry:
            f.write("\n")


def partitioner_report() -> None:
    """
    Generate report on the partitioning of vertices.
    """
    # Cycle through all vertices, and for each cycle through its vertices.
    # For each vertex, describe its core mapping.
    file_name = get_report_path("path_partitioner_reports")
    time_date_string = time.strftime("%c")
    try:
        with open(file_name, "w", encoding="utf-8") as f:
            progress = ProgressBar(FecDataView.get_n_vertices(),
                                   "Generating partitioner report")

            f.write("        Partitioning Information by Vertex\n")
            f.write("        ===============================\n\n")
            f.write(f"Generated: {time_date_string} for target machine "
                    f"'{FecDataView.get_ipaddress()}'\n\n")

            for vertex in progress.over(FecDataView.iterate_vertices()):
                _write_one_vertex_partition(f, vertex)
    except IOError:
        logger.exception(
            "Generate partitioning reports: Can't open file {} for writing.",
            file_name)


def _write_one_vertex_partition(f: TextIO, vertex: ApplicationVertex) -> None:
    vertex_name = vertex.label
    vertex_model = vertex.__class__.__name__
    num_atoms = vertex.n_atoms
    f.write(f"**** Vertex: '{vertex_name}'\n")
    f.write(f"Model: {vertex_model}\n")
    f.write(f"Pop size: {num_atoms}\n")
    f.write("Machine Vertices:\n")

    # Sort by slice and then by label
    machine_vertices = sorted(vertex.machine_vertices,
                              key=lambda x: x.label)
    machine_vertices = sorted(machine_vertices,
                              key=lambda x: x.vertex_slice.lo_atom)
    for sv in machine_vertices:
        f.write(f"  Slice {sv.vertex_slice}    Vertex {sv.label}\n")
    f.write("\n")


def placement_report_with_application_graph_by_vertex() -> None:
    """
    Generate report on the placement of vertices onto cores by vertex.
    """
    # Cycle through all vertices, and for each cycle through its vertices.
    # For each vertex, describe its core mapping.
    file_name = get_report_path("path_application_graph_placer_report_vertex")
    time_date_string = time.strftime("%c")
    try:
        with open(file_name, "w", encoding="utf-8") as f:
            progress = ProgressBar(FecDataView.get_n_vertices(),
                                   "Generating placement report")

            f.write("        Placement Information by Vertex\n")
            f.write("        ===============================\n\n")
            f.write(f"Generated: {time_date_string} "
                    f"for target machine '{FecDataView.get_ipaddress()}'\n\n")

            for vertex in progress.over(FecDataView.iterate_vertices()):
                _write_one_vertex_application_placement(f, vertex)
    except IOError:
        logger.exception(
            "Generate placement reports: Can't open file {} for writing.",
            file_name)


def _write_one_vertex_application_placement(
        f: TextIO, vertex: ApplicationVertex) -> None:
    vertex_name = vertex.label
    vertex_model = vertex.__class__.__name__
    num_atoms = vertex.n_atoms
    f.write(f"**** Vertex: '{vertex_name}'\n")
    f.write(f"Model: {vertex_model}\n")
    f.write(f"Pop size: {num_atoms}\n")
    f.write("Machine Vertices:\n")

    # Sort by slice and then by label
    machine_vertices = sorted(vertex.machine_vertices,
                              key=lambda vert: vert.label)
    machine_vertices = sorted(machine_vertices,
                              key=lambda vert: vert.vertex_slice.lo_atom)
    for sv in machine_vertices:
        if isinstance(sv, MachineSpiNNakerLinkVertex):
            f.write(f"  Slice {sv.vertex_slice} on "
                    f"SpiNNaker Link {sv.spinnaker_link_id}, "
                    f"board {sv.board_address}, "
                    f"linked to chip {sv.linked_chip_coordinates}\n")
        elif isinstance(sv, MachineFPGAVertex):
            f.write(f"  Slice {sv.vertex_slice} on FGPA {sv.fpga_id}, "
                    f"FPGA link {sv.fpga_link_id}, board {sv.board_address}, "
                    f"linked to chip {sv.linked_chip_coordinates}\n")
        else:
            cur_placement = FecDataView.get_placement_of_vertex(sv)
            x, y, p = cur_placement.x, cur_placement.y, cur_placement.p
            f.write(f"  Slice {sv.vertex_slice} on core ({x}, {y}, {p})"
                    f" {sv.label}\n")
    f.write("\n")


def placement_report_with_application_graph_by_core() -> None:
    """
    Generate report on the placement of vertices onto cores by core.
    """
    # File 2: Placement by core.
    # Cycle through all chips and by all cores within each chip.
    # For each core, display what is held on it.
    file_name = get_report_path("path_application_graph_placer_report_core")
    time_date_string = time.strftime("%c")
    try:
        machine = FecDataView.get_machine()
        with open(file_name, "w", encoding="utf-8") as f:
            progress = ProgressBar(machine.n_chips,
                                   "Generating placement by core report")

            f.write("        Placement Information by Core\n")
            f.write("        =============================\n\n")
            f.write(f"Generated: {time_date_string} "
                    f"for target machine '{FecDataView.get_ipaddress()}'\n\n")

            for chip in progress.over(machine.chips):
                _write_one_chip_application_placement(f, chip)
    except IOError:
        logger.exception(
            "Generate_placement_reports: Can't open file {} for writing.",
            file_name)


def _write_one_chip_application_placement(f: TextIO, chip: Chip) -> None:
    written_header = False
    total_sdram = None
    for placement in FecDataView.iterate_placements_on_core(chip):
        if not written_header:
            f.write(f"**** Chip: ({chip.x}, {chip.y})\n")
            f.write(f"Application cores: {chip.n_processors}\n")
            written_header = True
        pro_id = placement.p
        vertex = placement.vertex
        app_vertex = vertex.app_vertex
        if app_vertex is not None:
            vertex_label = app_vertex.label
            vertex_model = app_vertex.__class__.__name__
            vertex_atoms = app_vertex.n_atoms
            f.write(f"  Processor {pro_id}: Vertex: '{vertex_label}', "
                    f"pop size: {vertex_atoms}\n")
            f.write(f"              Slice: {vertex.vertex_slice}")
            f.write(f"  {vertex.label}\n")
            f.write(f"              Model: {vertex_model}\n")
        else:
            f.write(f"  Processor {pro_id}: System Vertex: '{vertex.label}'\n")
            f.write(f"              Model: {vertex.__class__.__name__}\n")

        sdram = vertex.sdram_required
        f.write(f"              {sdram.fixed}\n\n")
        if total_sdram is None:
            total_sdram = sdram
        else:
            total_sdram += sdram

    if total_sdram is not None:
        f.write(f"Total SDRAM on chip ({chip} available): "
                f"{total_sdram.fixed}; {total_sdram.per_timestep} "
                f"per-timestep\n\n")


def sdram_usage_report_per_chip() -> None:
    """
    Reports the SDRAM used per chip.
    """
    file_name = get_report_path("path_sdram_usage_report_per_chip")
    n_placements = FecDataView.get_n_placements()
    time_date_string = time.strftime("%c")
    progress = ProgressBar(
        (n_placements * 2 + FecDataView.get_machine().n_chips * 2),
        "Generating SDRAM usage report")
    try:
        with open(file_name, "w", encoding="utf-8") as f:
            f.write("        Memory Usage by Core\n")
            f.write("        ====================\n\n")
            f.write(f"Generated: {time_date_string} "
                    f"for target machine '{FecDataView.get_ipaddress()}'\n\n")
            f.write("Planned by partitioner\n")
            f.write("----------------------\n")
            _sdram_usage_report_per_chip_with_timesteps(
                f, FecDataView.get_plan_n_timestep(), progress, False, False)
            f.write("\nActual space reserved on the machine\n")
            f.write("----------------------\n")
            _sdram_usage_report_per_chip_with_timesteps(
                f, FecDataView.get_max_run_time_steps(), progress, True, True)
    except IOError:
        logger.exception("Generate_placement_reports: Can't open file {} for "
                         "writing.", file_name)


def _sdram_usage_report_per_chip_with_timesteps(
        f: TextIO, timesteps: Optional[int], progress: ProgressBar,
        end_progress: bool, details: bool) -> None:
    """
    :param f:
    :param timesteps: Either the plan or data timesteps
        depending on which is being reported
    :param progress:
    :param end_progress:
    :param details: If True will get costs printed by regions
    """
    f.write(f"Based on {timesteps} timesteps\n\n")
    sdram_by_chip = dict()
    placements = sorted(
        FecDataView.iterate_placemements(),
        key=lambda x: x.vertex.label or "")
    for placement in progress.over(placements, False):
        vertex_sdram = placement.vertex.sdram_required
        core_sdram = vertex_sdram.get_total_sdram(timesteps)
        x, y, p = placement.x, placement.y, placement.p
        if details:
            vertex_sdram.report(
                timesteps=timesteps,
                preamble=f"core ({x},{y},{p})", target=f)
        else:
            f.write(
                f"SDRAM reqs for core ({x},{y},{p}) is "
                f"{int(core_sdram / 1024.0)} KB ({core_sdram} bytes)"
                f" for {placement}\n")
        key = (x, y)
        if key not in sdram_by_chip:
            sdram_by_chip[key] = vertex_sdram
        else:
            sdram_by_chip[key] += vertex_sdram
    for chip in progress.over(FecDataView.get_machine().chips, end_progress):
        try:
            if chip in sdram_by_chip:
                chip_sdram = sdram_by_chip[chip]
                used_sdram = chip_sdram.get_total_sdram(timesteps)
                f.write(
                    f"**** Chip: ({chip.x}, {chip.y}) has total memory usage "
                    f"of {int(used_sdram / 1024.0)} KB ({used_sdram} bytes) "
                    f"out of a max of "
                    f"{int(chip.sdram / 1024.0)} KB ({chip.sdram} bytes)\n")
                f.write(
                    f"     Based on {chip_sdram}\n\n")

        except KeyError:
            # Do Nothing
            pass


def routing_info_report(extra_allocations: Iterable[
        Tuple[ApplicationVertex, str]] = ()) -> None:
    """
    Generates a report which says which keys is being allocated to each
    vertex.

    :param extra_allocations:
        Extra vertex/partition ID pairs to report on.
    """
    file_name = get_report_path("path_router_info_report")
    routing_infos = FecDataView.get_routing_infos()
    try:
        with open(file_name, "w", encoding="utf-8") as f:
            vertex_partitions = OrderedSet(
                (p.pre_vertex, p.identifier)
                for p in get_app_partitions())
            vertex_partitions.update(extra_allocations)
            progress = ProgressBar(len(vertex_partitions),
                                   "Generating Routing info report")
            for pre_vert, part_id in progress.over(vertex_partitions):
                _write_vertex_virtual_keys(f, pre_vert, part_id, routing_infos)
    except IOError:
        logger.exception("generate virtual key space information report: "
                         "Can't open file {} for writing.", file_name)


def _write_vertex_virtual_keys(
        f: TextIO, pre_vertex: ApplicationVertex, part_id: str,
        routing_infos: RoutingInfo) -> None:
    # If there are no outgoing machine vertices, then there is no routing
    outgoing = pre_vertex.splitter.get_out_going_vertices(part_id)
    if not outgoing:
        return
    rinfo = routing_infos.get_info_from(
        pre_vertex, part_id)
    f.write(f"Vertex: {pre_vertex}\n")
    f.write(f"    Partition: {part_id}, "
            f"Routing Info: {rinfo.key_and_mask}\n")
    for m_vertex in outgoing:
        r_info = routing_infos.get_info_from(
            m_vertex, part_id)
        f.write(f"    Machine Vertex: {m_vertex}, "
                f"Slice: {m_vertex.vertex_slice}, "
                f"Routing Info: {r_info.key_and_mask}\n")


def router_report_from_router_tables() -> None:
    """
    Report the uncompressed routing tables.
    """
    top_level_folder = get_report_path("path_uncompressed", is_dir=True)
    routing_tables = FecDataView.get_uncompressed().routing_tables
    if not os.path.exists(top_level_folder):
        os.mkdir(top_level_folder)
    progress = ProgressBar(routing_tables, "Generating Router table report")
    for routing_table in progress.over(routing_tables):
        if routing_table.number_of_entries:
            generate_routing_table(routing_table, top_level_folder)


def router_report_from_compressed_router_tables(
        routing_tables: MulticastRoutingTables) -> None:
    """
    Report the compressed routing tables.

    :param routing_tables: the compressed routing tables
    """
    top_level_folder = get_report_path("path_compressed", is_dir=True)
    if not os.path.exists(top_level_folder):
        os.mkdir(top_level_folder)
    progress = ProgressBar(routing_tables.routing_tables,
                           "Generating compressed router table report")
    for routing_table in progress.over(routing_tables.routing_tables):
        if routing_table.number_of_entries:
            generate_routing_table(routing_table, top_level_folder)


def generate_routing_table(routing_table: AbstractMulticastRoutingTable,
                           top_level_folder: str) -> None:
    """
    :param routing_table: The routing table to describe
    :param top_level_folder:
    """
    file_name = f"routing_table_{routing_table.x}_{routing_table.y}.rpt"
    file_path = os.path.join(top_level_folder, file_name)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(
                f"Router contains {routing_table.number_of_entries} entries\n")

            f.write(f'{"Index": <5s} {"Key": <10s} {"Mask": <10s} '
                    f'{"Route": <10s} {"Default": <7s} {"[Cores][Links]"}\n')
            f.write(
                f'{"":-<5s} {"":-<10s} {"":-<10s} '
                f'{"":-<10s} {"":-<7s} {"":-<14s}\n')
            line_format = "{: >5d} {}\n"

            entry_count = 0
            n_defaultable = 0
            for entry in routing_table.multicast_routing_entries:
                index = entry_count & _LOWER_16_BITS
                entry_str = line_format.format(index, format_route(entry))
                entry_count += 1
                if entry.defaultable:
                    n_defaultable += 1
                f.write(entry_str)
            f.write(f"{n_defaultable} Defaultable entries\n")
    except IOError:
        logger.exception("Generate_placement_reports: Can't open file"
                         " {} for writing.", file_path)


def _compression_ratio(uncompressed: int, compressed: int) -> float:
    """
    Get the compression ratio, as a percentage.
    """
    if uncompressed == 0:
        return 0
    return (uncompressed - compressed) / float(uncompressed) * 100


def generate_comparison_router_report(
        compressed_routing_tables: MulticastRoutingTables) -> None:
    """
    Make a report on comparison of the compressed and uncompressed
    routing tables.

    :param compressed_routing_tables: the compressed routing tables
    """
    routing_tables = FecDataView.get_uncompressed().routing_tables
    file_name = get_report_path("path_compression_comparison")
    try:
        with open(file_name, "w", encoding="utf-8") as f:
            progress = ProgressBar(
                routing_tables,
                "Generating comparison of router table report")
            total_uncompressed = 0
            total_compressed = 0
            max_compressed = 0
            uncompressed_for_max = 0
            for table in progress.over(routing_tables):
                x, y = table.x, table.y
                compressed_table = compressed_routing_tables.\
                    get_routing_table_for_chip(x, y)
                if compressed_table is None:
                    f.write(f"No compressed table at {x}:{y}; not compared!\n")
                    continue
                n_entries_uncompressed = table.number_of_entries
                total_uncompressed += n_entries_uncompressed
                n_entries_compressed = compressed_table.number_of_entries
                total_compressed += n_entries_compressed
                ratio = _compression_ratio(
                    n_entries_uncompressed, n_entries_compressed)
                f.write(
                    f"Uncompressed table at {x}:{y} has "
                    f"{n_entries_uncompressed} entries whereas compressed "
                    f"table has {n_entries_compressed} entries. This is a "
                    f"decrease of {ratio}%\n")
                if max_compressed < n_entries_compressed:
                    max_compressed = n_entries_compressed
                    uncompressed_for_max = n_entries_uncompressed
            if total_uncompressed > 0:
                ratio = _compression_ratio(
                    total_uncompressed, total_compressed)
                f.write(
                    f"\nTotal has {total_uncompressed} entries whereas "
                    f"compressed tables have {total_compressed} entries. "
                    f"This is an average decrease of {ratio}%\n")
                ratio = _compression_ratio(
                    uncompressed_for_max, max_compressed)
                f.write(
                    f"Worst case has {uncompressed_for_max} entries whereas "
                    f"compressed tables have {max_compressed} entries. This "
                    f"is a decrease of {ratio}%\n")
    except IOError:
        logger.exception(
            "Generate router comparison reports: "
            "Can't open file {} for writing.", file_name)


def _search_route(
        source_vertex: MachineVertex, key_and_mask: BaseKeyAndMask) -> str:
    # Create text for starting point
    machine = FecDataView.get_machine()
    text = ""
    # If the destination is virtual, replace with the real destination chip
    if isinstance(source_vertex, MachineSpiNNakerLinkVertex):
        slink = machine.get_spinnaker_link_with_id(
            source_vertex.spinnaker_link_id)
        x = slink.connected_chip_x
        y = slink.connected_chip_y
        text = f"        Virtual SpiNNaker Link {x}:{y} -> "
    elif isinstance(source_vertex, MachineFPGAVertex):
        flink = machine.get_fpga_link_with_id(
            source_vertex.fpga_id, source_vertex.fpga_link_id)
        x = flink.connected_chip_x
        y = flink.connected_chip_y
        text = f"        Virtual FPGA Link {x}:{y}-> "
    else:
        source_placement = FecDataView.get_placement_of_vertex(source_vertex)
        x = source_placement.x
        y = source_placement.y
        text = f"        {source_placement.x}:{source_placement.y}:" \
               f"{source_placement.p} -> "

    text += _recursive_trace_to_destinations(
        machine[x, y], key_and_mask, pre_space="        ")
    return text


# Locates the destinations of a route
def _recursive_trace_to_destinations(
        chip: Chip, key_and_mask: BaseKeyAndMask, pre_space: str) -> str:
    """
    Recursively search though routing tables till no more entries are
    registered with this key
    """
    text = f"-> Chip {chip.x}:{chip.y}"
    routing_tables = FecDataView.get_uncompressed()
    table = routing_tables.get_routing_table_for_chip(chip.x, chip.y)
    entry = _locate_routing_entry(table, key_and_mask.key)
    if entry is None:
        text += " -> No Entry"
    else:
        new_pre_space = pre_space + (" " * len(text))
        first = True
        for link_id in entry.link_ids:
            if not first:
                text += f"\n{pre_space}"
            link = chip.router.get_link(link_id)
            if link is None:
                text += f" -> ({link_id}) !!! no link !!!"
                continue
            text += f"-> {link}"
            if link is not None:
                text += _recursive_trace_to_destinations(
                    FecDataView.get_chip_at(
                        link.destination_x, link.destination_y),
                    key_and_mask, new_pre_space)
            first = False

    return text


def _locate_routing_entry(
        current_router: Optional[AbstractMulticastRoutingTable],
        key: int) -> Optional[MulticastRoutingEntry]:
    """
    Locate the entry from the router based off the edge

    :param current_router: the current router being used in the trace
    :param key: the key being used by the source placement
    :return: the routing table entry
    :raise PacmanRoutingException:
        when there is no entry located on this router.
    """
    if current_router is not None:
        for entry in current_router.multicast_routing_entries:
            if entry.mask & key == entry.key:
                return entry
    return None
