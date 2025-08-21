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
from spinn_utilities.progress_bar import ProgressBar
from spinnman.transceiver import Transceiver
from pacman.model.routing_tables import (
    AbstractMulticastRoutingTable, CompressedMulticastRoutingTable,
    MulticastRoutingTables)
from spinn_front_end_common.data import FecDataView


def read_routing_tables_from_machine() -> MulticastRoutingTables:
    """
    Reads compressed routing tables from a SpiNNaker machine.

    :returns: Routing tables after any compression on the machine
    """
    routing_tables = FecDataView.get_uncompressed()
    progress = ProgressBar(
        routing_tables, "Reading Routing Tables from Machine")
    app_id = FecDataView.get_app_id()
    transceiver = FecDataView.get_transceiver()

    machine_routing_tables = MulticastRoutingTables()
    for table in progress.over(routing_tables):
        # get multicast entries from machine
        machine_routing_table = _read_routing_table(
            transceiver, table, app_id)
        machine_routing_tables.add_routing_table(machine_routing_table)
    return machine_routing_tables


def _read_routing_table(
        transceiver: Transceiver, table: AbstractMulticastRoutingTable,
        app_id: int) -> CompressedMulticastRoutingTable:
    machine_routing_table = CompressedMulticastRoutingTable(table.x, table.y)
    for routing_entry in transceiver.get_multicast_routes(
            table.x, table.y, app_id):
        machine_routing_table.add_multicast_routing_entry(routing_entry)
    return machine_routing_table
