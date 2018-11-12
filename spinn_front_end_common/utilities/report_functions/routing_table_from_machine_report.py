import logging
import os
from spinn_utilities.progress_bar import ProgressBar
from pacman.model.routing_tables import (
    MulticastRoutingTable, MulticastRoutingTables)
from pacman.operations.algorithm_reports import reports

logger = logging.getLogger(__name__)

_FOLDER_NAME = "routing_tables_from_machine"


class RoutingTableFromMachineReport(object):
    def __call__(
            self, report_default_directory, routing_tables, transceiver,
            app_id):
        # pylint: disable=protected-access
        tables = list(routing_tables.routing_tables)
        progress = ProgressBar(tables, "Reading Routing Tables from Machine")

        folder_name = os.path.join(report_default_directory, _FOLDER_NAME)
        os.mkdir(folder_name)

        machine_routing_tables = MulticastRoutingTables()

        # generate a file for every multicast entry
        for routing_table in progress.over(tables):
            # get multicast entries from machine
            machine_routing_table = self._read_routing_table(
                transceiver, routing_table, app_id)
            machine_routing_tables.add_routing_table(machine_routing_table)
            reports._generate_routing_table(machine_routing_table, folder_name)

        return machine_routing_tables

    def _read_routing_table(self, txrx, table, app_id):
        machine_routing_table = MulticastRoutingTable(table.x, table.y)
        for routing_entry in txrx.get_multicast_routes(
                table.x, table.y, app_id):
            machine_routing_table.add_multicast_routing_entry(routing_entry)
        return machine_routing_table
