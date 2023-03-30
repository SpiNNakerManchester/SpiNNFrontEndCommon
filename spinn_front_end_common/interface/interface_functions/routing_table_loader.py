# Copyright (c) 2015 The University of Manchester
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

from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.data import FecDataView


def routing_table_loader(router_tables):
    """
    Loads routes into initialised routers.

    :param ~pacman.model.routing_tables.MulticastRoutingTables router_tables:
    """
    progress = ProgressBar(router_tables.routing_tables,
                           "Loading routing data onto the machine")

    # load each router table that is needed for the application to run into
    # the chips SDRAM
    app_id = FecDataView.get_app_id()
    transceiver = FecDataView.get_transceiver()
    for table in progress.over(router_tables.routing_tables):
        if (table.number_of_entries):
            transceiver.load_multicast_routes(
                table.x, table.y, table.multicast_routing_entries,
                app_id)
