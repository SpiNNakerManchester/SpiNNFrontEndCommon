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
from spinn_utilities.config_holder import get_report_path
from spinn_utilities.log import FormatAdapter
from spinn_utilities.progress_bar import ProgressBar
from pacman.model.routing_tables import MulticastRoutingTables
from pacman.operations.router_compressors.routing_compression_checker import (
    codify_table, compare_route)
from pacman.utilities.algorithm_utilities.routes_format import format_route
logger = FormatAdapter(logging.getLogger(__name__))


def generate_routing_compression_checker_report(
        routing_tables: MulticastRoutingTables,
        compressed_routing_tables: MulticastRoutingTables) -> None:
    """
    Make a full report of how the compressed covers all routes in the
    and uncompressed routing table.

    :param routing_tables: the original routing tables
    :param compressed_routing_tables: the compressed routing tables
    """
    file_name = get_report_path(
        section="Mapping", option="path_compression_checker")

    try:
        with open(file_name, "w", encoding="utf-8") as f:
            progress = ProgressBar(
                routing_tables.routing_tables,
                "Generating routing compression checker report")
            f.write("If this table did not raise an exception compression "
                    "was fully checked.\n\n")
            f.write("The format is:\n"
                    "Chip x, y\n"
                    "\t Uncompressed Route\n"
                    "\t\tCompressed Route\n\n")

            for original in progress.over(routing_tables.routing_tables):
                x, y = original.x, original.y
                f.write(f"Chip: X:{x} Y:{y}\n")

                compressed_table = compressed_routing_tables.\
                    get_routing_table_for_chip(x, y)
                assert compressed_table is not None
                compressed_dict = codify_table(compressed_table)
                for o_route in original.multicast_routing_entries:
                    f.write(f"\t{format_route(o_route)}\n")
                    compare_route(o_route, compressed_dict, f=f)
    except IOError:
        logger.exception(
            "Generate router comparison reports: "
            "Can't open file {} for writing.", file_name)
