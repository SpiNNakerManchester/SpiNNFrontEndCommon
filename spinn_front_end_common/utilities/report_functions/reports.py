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
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from spinn_machine import Router
from pacman import exceptions
from pacman.model.graphs.machine import (
    MachineFPGAVertex, MachineSpiNNakerLinkVertex)
from pacman.utilities.algorithm_utilities.routing_algorithm_utilities import (
    get_app_partitions)
from pacman.utilities.algorithm_utilities.routes_format import format_route
from spinn_front_end_common.data import FecDataView
from .router_summary import RouterSummary

logger = FormatAdapter(logging.getLogger(__name__))

_LINK_LABELS = {0: 'E', 1: 'NE', 2: 'N', 3: 'W', 4: 'SW', 5: 'S'}

_C_ROUTING_TABLE_DIR = "compressed_routing_tables_generated"
_COMPARED_FILENAME = "comparison_of_compressed_uncompressed_routing_tables.rpt"
_COMPRESSED_ROUTING_SUMMARY_FILENAME = "compressed_routing_summary.rpt"
_PARTITIONING_FILENAME = "partitioned_by_vertex.rpt"
_PLACEMENT_VTX_GRAPH_FILENAME = "placement_by_vertex_using_graph.rpt"
_PLACEMENT_VTX_SIMPLE_FILENAME = "placement_by_vertex_without_graph.rpt"
_PLACEMENT_CORE_GRAPH_FILENAME = "placement_by_core_using_graph.rpt"
_PLACEMENT_CORE_SIMPLE_FILENAME = "placement_by_core_without_graph.rpt"
_ROUTING_FILENAME = "edge_routing_info.rpt"
_ROUTING_SUMMARY_FILENAME = "routing_summary.rpt"
_ROUTING_TABLE_DIR = "routing_tables_generated"
_SDRAM_FILENAME = "chip_sdram_usage_by_core.rpt"
_TAGS_FILENAME = "tags.rpt"
_VIRTKEY_FILENAME = "virtual_key_space_information_report.rpt"

_LOWER_16_BITS = 0xFFFF


def tag_allocator_report():
    """
    Reports the tags that are being used by the tool chain for this
    simulation.
    """
    tag_infos = FecDataView.get_tags()
    file_name = os.path.join(FecDataView.get_run_dir_path(), _TAGS_FILENAME)
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


def placer_reports_with_application_graph():
    """
    Reports that can be produced from placement given a application
    graph's existence.
    """
    placement_report_with_application_graph_by_vertex()
    placement_report_with_application_graph_by_core()


def router_summary_report():
    """
    Generates a text file of routing summaries.

    :rtype: RouterSummary
    """
    file_name = os.path.join(
        FecDataView.get_run_dir_path(), _ROUTING_SUMMARY_FILENAME)
    progress = ProgressBar(FecDataView.get_machine().n_chips,
                           "Generating Routing summary report")
    routing_tables = FecDataView.get_uncompressed()
    return _do_router_summary_report(file_name, progress, routing_tables)


def router_compressed_summary_report(routing_tables):
    """
    Generates a text file of routing summaries.

    :param ~pacman.model.routing_tables.MulticastRoutingTables routing_tables:
        The in-operation COMPRESSED routing tables.
    :rtype: RouterSummary
    """
    file_name = os.path.join(
        FecDataView.get_run_dir_path(), _COMPRESSED_ROUTING_SUMMARY_FILENAME)
    progress = ProgressBar(FecDataView.get_machine().n_chips,
                           "Generating Routing summary report")
    return _do_router_summary_report(file_name, progress, routing_tables)


def _do_router_summary_report(file_name, progress, routing_tables):
    """
    :param str file_name:
    :param ~spinn_utilities.progress_bar.Progress progress:
    :param ~pacman.model.routing_tables.MulticastRoutingTables routing_tables:
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


def router_report_from_paths():
    """
    Generates a text file of routing paths.
    """
    file_name = os.path.join(FecDataView.get_run_dir_path(), _ROUTING_FILENAME)
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


def _write_one_router_partition_report(f, partition):
    """
    :param ~io.FileIO f:
    :param AbstractSingleSourcePartition partition:
    """
    source = partition.pre_vertex
    outgoing = source.splitter.get_out_going_vertices(partition.identifier)
    f.write(f"Source Application vertex {source}, partition"
            f" {partition.identifier}\n")

    routing_infos = FecDataView.get_routing_infos()
    for edge in partition.edges:
        for m_vertex in outgoing:
            source_placement = FecDataView.get_placement_of_vertex(m_vertex)
            r_info = routing_infos.get_routing_info_from_pre_vertex(
                m_vertex, partition.identifier)
            path = _search_route(source_placement, r_info.key_and_mask)
            f.write(
                f"    Edge '{edge.label}', "
                f"from vertex: '{edge.pre_vertex.label}' "
                f"to vertex: '{edge.post_vertex.label}'{path}\n")

            # End one entry:
            f.write("\n")


def partitioner_report():
    """
    Generate report on the partitioning of vertices.
    """
    # Cycle through all vertices, and for each cycle through its vertices.
    # For each vertex, describe its core mapping.
    file_name = os.path.join(
        FecDataView.get_run_dir_path(), _PARTITIONING_FILENAME)
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


def _write_one_vertex_partition(f, vertex):
    """
    :param ~io.FileIO f:
    :param ~pacman.model.graphs.application.ApplicationVertex vertex:
    """
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
        f.write(f"  Slice {sv.vertex_slice}\n")
    f.write("\n")


def placement_report_with_application_graph_by_vertex():
    """
    Generate report on the placement of vertices onto cores by vertex.
    """
    # Cycle through all vertices, and for each cycle through its vertices.
    # For each vertex, describe its core mapping.
    file_name = os.path.join(
        FecDataView.get_run_dir_path(), _PLACEMENT_VTX_GRAPH_FILENAME)
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


def _write_one_vertex_application_placement(f, vertex):
    """
    :param ~io.FileIO f:
    :param ~pacman.model.graphs.application.ApplicationVertex vertex:
    """
    vertex_name = vertex.label
    vertex_model = vertex.__class__.__name__
    num_atoms = vertex.n_atoms
    f.write(f"**** Vertex: '{vertex_name}'\n")
    f.write(f"Model: {vertex_model}\n")
    f.write(f"Pop size: {num_atoms}\n")
    f.write("Machine Vertices: \n")

    # Sort by slice and then by label
    machine_vertices = sorted(vertex.machine_vertices,
                              key=lambda vert: vert.label)
    machine_vertices = sorted(machine_vertices,
                              key=lambda vert: vert.vertex_slice.lo_atom)
    for sv in machine_vertices:
        if isinstance(sv, MachineSpiNNakerLinkVertex):
            f.write("  Slice {} on SpiNNaker Link {}, board {},"
                    " linked to chip {}\n"
                    .format(sv.vertex_slice, sv.spinnaker_link_id,
                            sv.board_address, sv.linked_chip_coordinates))
        elif isinstance(sv, MachineFPGAVertex):
            f.write("  Slice {} on FGPA {}, FPGA link {}, board {},"
                    " linked to chip {}\n"
                    .format(sv.vertex_slice, sv.fpga_id, sv.fpga_link_id,
                            sv.board_address, sv.linked_chip_coordinates))
        else:
            cur_placement = FecDataView.get_placement_of_vertex(sv)
            x, y, p = cur_placement.x, cur_placement.y, cur_placement.p
            f.write(f"  Slice {sv.vertex_slice} on core ({x}, {y}, {p}) \n")
    f.write("\n")


def placement_report_with_application_graph_by_core():
    """
    Generate report on the placement of vertices onto cores by core.
    """
    # File 2: Placement by core.
    # Cycle through all chips and by all cores within each chip.
    # For each core, display what is held on it.
    file_name = os.path.join(
        FecDataView.get_run_dir_path(), _PLACEMENT_CORE_GRAPH_FILENAME)
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


def _write_one_chip_application_placement(f, chip):
    """
    :param ~io.FileIO f:
    :param ~spinn_machine.Chip chip:
    :param ~pacman.model.placements.Placements placements:
    """
    written_header = False
    total_sdram = None
    for placement in FecDataView.iterate_placements_on_core(chip.x, chip.y):
        if not written_header:
            f.write(f"**** Chip: ({chip.x}, {chip.y})\n")
            f.write(f"Application cores: {len(list(chip.processors))}\n")
            written_header = True
        pro_id = placement.p
        vertex = placement.vertex
        app_vertex = vertex.app_vertex
        if app_vertex is not None:
            vertex_label = app_vertex.label
            vertex_model = app_vertex.__class__.__name__
            vertex_atoms = app_vertex.n_atoms
            f.write("  Processor {}: Vertex: '{}', pop size: {}\n".format(
                pro_id, vertex_label, vertex_atoms))
            f.write("              Slice on this core: {}\n".format(
                vertex.vertex_slice))
            f.write("              Model: {}\n".format(vertex_model))
        else:
            f.write("  Processor {}: System Vertex: '{}'\n".format(
                pro_id, vertex.label))
            f.write("              Model: {}\n".format(
                vertex.__class__.__name__))

        sdram = vertex.sdram_required
        f.write("              SDRAM required: {}; {} per timestep\n\n"
                .format(sdram.fixed, sdram.per_timestep))
        if total_sdram is None:
            total_sdram = sdram
        else:
            total_sdram += sdram

    if total_sdram is not None:
        f.write("Total SDRAM on chip ({} available): {}; {} per-timestep\n\n"
                .format(chip.sdram.size, total_sdram.fixed,
                        total_sdram.per_timestep))


def sdram_usage_report_per_chip():
    """
    Reports the SDRAM used per chip.
    """
    file_name = os.path.join(FecDataView.get_run_dir_path(), _SDRAM_FILENAME)
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
        f, timesteps, progress, end_progress, details):
    """
    :param ~io.FileIO f:
    :param int timesteps: Either the plan or data timesteps
        depending on which is being reported
    :param ~spinn_utilities.progress_bar.ProgressBar progress:
    :param bool end_progress:
    :param bool details: If True will get costs printed by regions
    """
    f.write(f"Based on {timesteps} timesteps\n\n")
    used_sdram_by_chip = dict()
    placements = sorted(
        FecDataView.iterate_placemements(), key=lambda x: x.vertex.label)
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
                "SDRAM reqs for core ({},{},{}) is {} KB ({} bytes) for {}\n"
                "".format(x, y, p, int(core_sdram / 1024.0), core_sdram,
                          placement))
        key = (x, y)
        if key not in used_sdram_by_chip:
            used_sdram_by_chip[key] = core_sdram
        else:
            used_sdram_by_chip[key] += core_sdram
    for chip in progress.over(FecDataView.get_machine().chips, end_progress):
        try:
            used_sdram = used_sdram_by_chip[chip.x, chip.y]
            if used_sdram:
                f.write(
                    "**** Chip: ({}, {}) has total memory usage of"
                    " {} KB ({} bytes) out of a max of "
                    "{} KB ({} bytes)\n\n".format(
                        chip.x, chip.y,
                        int(used_sdram / 1024.0), used_sdram,
                        int(chip.sdram.size / 1024.0), chip.sdram.size))
        except KeyError:
            # Do Nothing
            pass


def routing_info_report(extra_allocations):
    """
    Generates a report which says which keys is being allocated to each
    vertex.
    """
    file_name = os.path.join(FecDataView.get_run_dir_path(), _VIRTKEY_FILENAME)
    routing_infos = FecDataView.get_routing_infos()
    try:
        with open(file_name, "w", encoding="utf-8") as f:
            vertex_partitions = set(
                (p.pre_vertex, p.identifier)
                for p in FecDataView.iterate_partitions())
            vertex_partitions.update(extra_allocations)
            progress = ProgressBar(len(vertex_partitions),
                                   "Generating Routing info report")
            for pre_vert, part_id in progress.over(vertex_partitions):
                _write_vertex_virtual_keys(f, pre_vert, part_id, routing_infos)
            progress.end()
    except IOError:
        logger.exception("generate virtual key space information report: "
                         "Can't open file {} for writing.", file_name)


def _write_vertex_virtual_keys(f, pre_vertex, part_id, routing_infos):
    """
    :param ~io.FileIO f:
    :param ~pacman.model.graphs.application.ApplicationVertex pre_vertex:
    :param str part_id:
    :param ~pacman.model.routing_info.RoutingInfo routing_infos:
    :param ~spinn_utilities.progress_bar.ProgressBar progress:
    """
    rinfo = routing_infos.get_routing_info_from_pre_vertex(
        pre_vertex, part_id)
    # Might be None if the partition has no outgoing vertices e.g. a Poisson
    # source replaced by SDRAM comms
    if rinfo is not None:
        f.write(f"Vertex: {pre_vertex}\n")
        f.write("    Partition: {}, Routing Info: {}\n".format(
            part_id, rinfo.key_and_mask))
        for m_vertex in pre_vertex.splitter.get_out_going_vertices(part_id):
            r_info = routing_infos.get_routing_info_from_pre_vertex(
                m_vertex, part_id)
            if r_info is not None:
                f.write("    Machine Vertex: {}, Slice: {}, Routing Info: {}\n"
                        .format(m_vertex, m_vertex.vertex_slice,
                                r_info.key_and_mask))


def router_report_from_router_tables():
    """
    Report the uncompressed routing tables.
    """
    top_level_folder = os.path.join(
        FecDataView.get_run_dir_path(), _ROUTING_TABLE_DIR)
    routing_tables = FecDataView.get_uncompressed().routing_tables
    if not os.path.exists(top_level_folder):
        os.mkdir(top_level_folder)
    progress = ProgressBar(routing_tables, "Generating Router table report")
    for routing_table in progress.over(routing_tables):
        if routing_table.number_of_entries:
            generate_routing_table(routing_table, top_level_folder)


def router_report_from_compressed_router_tables(routing_tables):
    """
    Report the compressed routing tables.

    :param ~pacman.model.routing_tables.MulticastRoutingTables routing_tables:
        the compressed routing tables
    """
    top_level_folder = os.path.join(
        FecDataView.get_run_dir_path(), _C_ROUTING_TABLE_DIR)
    if not os.path.exists(top_level_folder):
        os.mkdir(top_level_folder)
    progress = ProgressBar(routing_tables.routing_tables,
                           "Generating compressed router table report")
    for routing_table in progress.over(routing_tables.routing_tables):
        if routing_table.number_of_entries:
            generate_routing_table(routing_table, top_level_folder)


def generate_routing_table(routing_table, top_level_folder):
    """
    :param routing_table: The routing table to describe
    :type routing_table:
        ~pacman.model.routing_tables.AbstractMulticastRoutingTable
    :param str top_level_folder:
    """
    file_name = "routing_table_{}_{}.rpt".format(
        routing_table.x, routing_table.y)
    file_path = os.path.join(top_level_folder, file_name)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Router contains {} entries\n".format(
                routing_table.number_of_entries))

            f.write("{: <5s} {: <10s} {: <10s} {: <10s} {: <7s} {}\n".format(
                "Index", "Key", "Mask", "Route", "Default", "[Cores][Links]"))
            f.write(
                "{:-<5s} {:-<10s} {:-<10s} {:-<10s} {:-<7s} {:-<14s}\n".format(
                    "", "", "", "", "", ""))
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


def _compression_ratio(uncompressed, compressed):
    """
    Get the compression ratio, as a percentage.

    :param int uncompressed:
    :param int compressed:
    :rtype: float
    """
    if uncompressed == 0:
        return 0
    return (uncompressed - compressed) / float(uncompressed) * 100


def generate_comparison_router_report(compressed_routing_tables):
    """
    Make a report on comparison of the compressed and uncompressed
    routing tables.

    :param compressed_routing_tables: the compressed routing tables
    :type compressed_routing_tables:
        ~pacman.model.routing_tables.MulticastRoutingTables
    """
    routing_tables = FecDataView.get_uncompressed().routing_tables
    file_name = os.path.join(
        FecDataView.get_run_dir_path(), _COMPARED_FILENAME)
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
                x = table.x
                y = table.y
                compressed_table = compressed_routing_tables.\
                    get_routing_table_for_chip(x, y)
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


def _search_route(source_placement, key_and_mask):
    """
    :param ~pacman.model.placements.Placement source_placement:
    :param ~pacman.model.routing_info.BaseKeyAndMask key_and_mask:
    :rtype: tuple(str, int)
    """
    # Create text for starting point
    machine = FecDataView.get_machine()
    source_vertex = source_placement.vertex
    text = ""
    if isinstance(source_vertex, MachineSpiNNakerLinkVertex):
        text = "        Virtual SpiNNaker Link on {}:{}:{} -> ".format(
            source_placement.x, source_placement.y, source_placement.p)
        slink = machine.get_spinnaker_link_with_id(
            source_vertex.spinnaker_link_id)
        x = slink.connected_chip_x
        y = slink.connected_chip_y
    elif isinstance(source_vertex, MachineFPGAVertex):
        text = "        Virtual FPGA Link on {}:{}:{} -> ".format(
            source_placement.x, source_placement.y, source_placement.p)
        flink = machine.get_fpga_link_with_id(
            source_vertex.fpga_id, source_vertex.fpga_link_id)
        x = flink.connected_chip_x
        y = flink.connected_chip_y
    else:
        x = source_placement.x
        y = source_placement.y
        text = "        {}:{}:{} -> ".format(
            source_placement.x, source_placement.y, source_placement.p)

    # If the destination is virtual, replace with the real destination chip
    text += _recursive_trace_to_destinations(
        x, y, key_and_mask, pre_space="        ")
    return text


# Locates the destinations of a route
def _recursive_trace_to_destinations(
        chip_x, chip_y, key_and_mask, pre_space):
    """
    Recursively search though routing tables till no more entries are
    registered with this key

    :param int chip_x:
    :param int chip_y
    :param ~pacman.model.routing_info.BaseKeyAndMask key_and_mask:
    :rtype: str
    """
    chip = FecDataView.get_chip_at(chip_x, chip_y)

    text = f"-> Chip {chip_x}:{chip_y}"
    routing_tables = FecDataView.get_uncompressed()
    table = routing_tables.get_routing_table_for_chip(chip_x, chip_y)
    entry = _locate_routing_entry(table, key_and_mask.key)
    new_pre_space = pre_space + (" " * len(text))
    first = True
    for link_id in entry.link_ids:
        if not first:
            text += f"\n{pre_space}"
        link = chip.router.get_link(link_id)
        text += f"-> {link}"
        text += _recursive_trace_to_destinations(
            link.destination_x, link.destination_y, key_and_mask,
            new_pre_space)
        first = False

    return text


def _locate_routing_entry(current_router, key):
    """
    Locate the entry from the router based off the edge

    :param ~spinn_machine.MulticastRoutingTable current_router:
        the current router being used in the trace
    :param int key: the key being used by the source placement
    :return: the routing table entry
    :rtype: ~spinn_machine.MulticastRoutingEntry
    :raise PacmanRoutingException:
        when there is no entry located on this router.
    """
    for entry in current_router.multicast_routing_entries:
        if entry.mask & key == entry.routing_entry_key:
            return entry
    raise exceptions.PacmanRoutingException("no entry located")
