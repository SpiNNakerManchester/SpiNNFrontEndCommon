# Copyright (c) 2017-2019 The University of Manchester
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
from spinn_utilities.log import FormatAdapter
from spinn_utilities.progress_bar import ProgressBar
from pacman.operations.router_compressors.routing_compression_checker import (
    codify_table, compare_route)
from pacman.utilities.algorithm_utilities.routes_format import format_route
from spinn_front_end_common.data import FecDataView
logger = FormatAdapter(logging.getLogger(__name__))


def generate_routing_compression_checker_report(
        routing_tables, compressed_routing_tables):
    """ Make a full report of how the compressed covers all routes in the\
        and uncompressed routing table

    :param str report_folder: the folder to store the resulting report
    :param MulticastRoutingTables routing_tables: the original routing tables
    :param MulticastRoutingTables compressed_routing_tables:
        the compressed routing tables
    :rtype: None
    """
    file_name = os.path.join(
        FecDataView.get_run_dir_path(),
        "routing_compression_checker_report.rpt")

    try:
        with open(file_name, "w") as f:
            progress = ProgressBar(
                routing_tables.routing_tables,
                "Generating routing compression checker report")
            f.write("If this table did not raise an exception compression "
                    "was fully checked. \n\n")
            f.write("The format is:\n"
                    "Chip x, y\n"
                    "\t Uncompressed Route\n"
                    "\t\tCompressed Route\n\n")

            for original in progress.over(routing_tables.routing_tables):
                x = original.x
                y = original.y
                f.write("Chip: X:{} Y:{} \n".format(x, y))

                compressed_table = compressed_routing_tables.\
                    get_routing_table_for_chip(x, y)
                compressed_dict = codify_table(compressed_table)
                for o_route in original.multicast_routing_entries:
                    f.write("\t{}\n".format(format_route(o_route)))
                    compare_route(o_route, compressed_dict, f=f)
    except IOError:
        logger.exception("Generate_router_comparison_reports: Can't open file"
                         " {} for writing.", file_name)
