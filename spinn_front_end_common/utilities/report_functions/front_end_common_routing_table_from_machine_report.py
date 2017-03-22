from pacman.model.routing_tables.multicast_routing_table import \
    MulticastRoutingTable
from pacman.operations.algorithm_reports import reports

from spinn_front_end_common.utilities import exceptions

from spinn_machine.utilities.progress_bar import ProgressBar

import logging
import os

logger = logging.getLogger(__name__)


class FrontEndCommonRoutingTableFromMachineReport(object):
    def __call__(
            self, report_default_directory, routing_tables, transceiver,
            app_id, has_loaded_routing_tables_flag):

        progress = ProgressBar(
            len(list(routing_tables.routing_tables)),
            "Reading Routing Tables from Machine")

        if not has_loaded_routing_tables_flag:
            raise exceptions.ConfigurationException(
                "This report needs the routing tables to be loaded onto the "
                "machine before being executed.")

        folder_name = os.path.join(
            report_default_directory, "routing_tables_from_machine")

        os.mkdir(folder_name)

        # generate a file for every multicast entry
        for routing_table in routing_tables:

            # get multicast entries from machine
            multi_cast_entries = transceiver.get_multicast_routes(
                routing_table.x, routing_table.y, app_id)

            machine_routing_table = \
                MulticastRoutingTable(routing_table.x, routing_table.y)

            for multi_cast_entry in multi_cast_entries:
                machine_routing_table.add_multicast_routing_entry(
                    multi_cast_entry)

            reports._generate_routing_table(machine_routing_table, folder_name)
            progress.update()
        progress.end()
