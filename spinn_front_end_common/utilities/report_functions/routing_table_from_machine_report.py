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
import os
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.report_functions import reports

_FOLDER_NAME = "routing_tables_from_machine"


def routing_table_from_machine_report(routing_tables):
    """ Report the routing table that was actually on the machine.

        folder_name = os.path.join(FecDataView().run_dir_path, _FOLDER_NAME)
        os.mkdir(folder_name)
    :param routing_tables:
    :type routing_tables:
        ~pacman.model.routing_tables.MulticastRoutingTables
    :param ~spinnman.transceiver.Transceiver transceiver:
    :param int app_id:
    """
    # pylint: disable=protected-access
    tables = list(routing_tables.routing_tables)
    progress = ProgressBar(tables, "Reading Routing Tables from Machine")

    folder_name = os.path.join(FecDataView().run_dir_path, _FOLDER_NAME)
    os.mkdir(folder_name)

    # generate a file for every multicast entry
    for routing_table in progress.over(tables):
        reports.generate_routing_table(routing_table, folder_name)
