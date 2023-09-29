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
import os
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.report_functions import reports

_FOLDER_NAME = "routing_tables_from_machine"


def routing_table_from_machine_report(routing_tables):
    """
    Report the routing table that was actually on the machine.

        folder_name = os.path.join(FecDataView().run_dir_path, _FOLDER_NAME)
        os.mkdir(folder_name)

    :param routing_tables: Compressed routing tables
    :type routing_tables:
        ~pacman.model.routing_tables.MulticastRoutingTables
    :param ~spinnman.transceiver.Transceiver transceiver:
    :param int app_id:
    """
    tables = list(routing_tables.routing_tables)
    progress = ProgressBar(tables, "Reading Routing Tables from Machine")

    folder_name = os.path.join(FecDataView.get_run_dir_path(), _FOLDER_NAME)
    os.mkdir(folder_name)

    # generate a file for every multicast entry
    for routing_table in progress.over(tables):
        reports.generate_routing_table(routing_table, folder_name)
