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


class RoutingTableLoader(object):
    """ Loads routes into initialised routers.
    """
    __slots__ = []

    def __call__(self, router_tables, app_id, transceiver, machine):
        """
        :param router_tables:
        :type router_tables:
            ~pacman.model.routing_tables.MulticastRoutingTables
        :param int app_id:
        :param ~spinnman.transceiver.Transceiver transceiver:
        :param ~spinn_machine.Machine machine:
        """
        progress = ProgressBar(router_tables.routing_tables,
                               "Loading routing data onto the machine")

        # load each router table that is needed for the application to run into
        # the chips SDRAM
        for table in progress.over(router_tables.routing_tables):
            if (not machine.get_chip_at(table.x, table.y).virtual
                    and table.multicast_routing_entries):
                transceiver.load_multicast_routes(
                    table.x, table.y, table.multicast_routing_entries,
                    app_id=app_id)
