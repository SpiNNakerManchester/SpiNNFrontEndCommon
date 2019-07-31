from pacman.model.routing_tables import MulticastRoutingTables
from pacman.model.routing_tables.compressed_multicast_routing_table import \
    CompressedMulticastRoutingTable
from spinn_utilities.progress_bar import ProgressBar


class ReadRoutingTablesFromMachine(object):

    def __call__(self, transceiver, routing_tables, app_id):

        progress = ProgressBar(
            routing_tables, "Reading Routing Tables from Machine")
        machine_routing_tables = MulticastRoutingTables()
        for routing_table in progress.over(routing_tables):
            # get multicast entries from machine
            machine_routing_table = self._read_routing_table(
                transceiver, routing_table, app_id)
            machine_routing_tables.add_routing_table(machine_routing_table)

        return machine_routing_tables

    @staticmethod
    def _read_routing_table(transceiver, table, app_id):
        machine_routing_table = \
            CompressedMulticastRoutingTable(table.x, table.y)
        for routing_entry in transceiver.get_multicast_routes(
                table.x, table.y, app_id):
            machine_routing_table.add_multicast_routing_entry(routing_entry)
        return machine_routing_table
