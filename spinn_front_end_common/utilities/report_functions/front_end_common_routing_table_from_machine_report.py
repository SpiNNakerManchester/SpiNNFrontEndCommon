from spinn_utilities.progress_bar import ProgressBar
from pacman.model.routing_tables.multicast_routing_table import \
    MulticastRoutingTable
from pacman.operations.algorithm_reports import reports

from spinn_front_end_common.utilities import exceptions

import logging
import os

logger = logging.getLogger(__name__)


class FrontEndCommonRoutingTableFromMachineReport(object):
    def __call__(
            self, report_default_directory, routing_tables, transceiver,
            app_id, has_loaded_routing_tables_flag):
        if not has_loaded_routing_tables_flag:
            raise exceptions.ConfigurationException(
                "This report needs the routing tables to be loaded onto the "
                "machine before being executed.")

        tables = list(routing_tables.routing_tables)
        progress = ProgressBar(tables, "Reading Routing Tables from Machine")

        folder_name = os.path.join(
            report_default_directory, "routing_tables_from_machine")

        os.mkdir(folder_name)

        # generate a file for every multicast entry
        for routing_table in progress.over(tables):
            # get multicast entries from machine
            machine_routing_table = self._read_routing_table(
                transceiver, routing_table, app_id)
            reports._generate_routing_table(machine_routing_table, folder_name)

    def _read_routing_table(self, txrx, routing_table, app_id):
        machine_routing_table = \
            MulticastRoutingTable(routing_table.x, routing_table.y)
        for routing_entry in txrx.get_multicast_routes(
                routing_table.x, routing_table.y, app_id):
            machine_routing_table.add_multicast_routing_entry(routing_entry)
        return machine_routing_table
