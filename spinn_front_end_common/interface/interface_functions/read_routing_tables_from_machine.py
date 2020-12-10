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
from spinn_utilities.progress_bar import ProgressBar
from pacman.model.routing_tables import MulticastRoutingTables
from pacman.model.routing_tables.compressed_multicast_routing_table import (
    CompressedMulticastRoutingTable)


class ReadRoutingTablesFromMachine(object):
    """ Reads compressed routing tables from a SpiNNaker machine.
    """

    def __call__(self, transceiver, routing_tables, app_id):
        """
        :param ~spinnman.transceiver.Transceiver transceiver:
        :param routing_tables: uncompressed routing tables
        :type routing_tables:
            ~pacman.model.routing_tables.MulticastRoutingTables
        :param int app_id:
        :rtype: ~pacman.model.routing_tables.MulticastRoutingTables
        """

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
        """
        :param ~spinnman.transceiver.Transceiver transceiver:
        :param ~.UnCompressedMulticastRoutingTable table:
        :param int app_id:
        """
        machine_routing_table = \
            CompressedMulticastRoutingTable(table.x, table.y)
        for routing_entry in transceiver.get_multicast_routes(
                table.x, table.y, app_id):
            machine_routing_table.add_multicast_routing_entry(routing_entry)
        return machine_routing_table
