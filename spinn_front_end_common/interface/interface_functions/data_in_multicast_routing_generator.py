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

from pacman.exceptions import (PacmanRoutingException)
from pacman.model.routing_tables import (
    MulticastRoutingTables, MulticastRoutingTable)
from spinn_machine import MulticastRoutingEntry
from spinn_utilities.progress_bar import ProgressBar

N_KEYS_PER_PARTITION_ID = 4
KEY_START_VALUE = 4
ROUTING_MASK = 0xFFFFFFFC


class DataInMulticastRoutingGenerator(object):
    """ Generates routing table entries used by the data in processes with the\
    extra monitor cores.
    """
    __slots__ = ["_monitors", "_machine", "_key_to_destination_map",
                 "_placements", "_routing_tables"]

    def __call__(self, machine, extra_monitor_cores, placements):
        # pylint: disable=attribute-defined-outside-init
        self._machine = machine
        self._placements = placements
        self._monitors = extra_monitor_cores
        self._routing_tables = MulticastRoutingTables()
        self._key_to_destination_map = dict()
        # create progress bar
        progress = ProgressBar(
            machine.ethernet_connected_chips,
            "Generating routing tables for data in system processes")

        for ethernet_chip in progress.over(machine.ethernet_connected_chips):
            tree = self._generate_routing_tree(ethernet_chip)
            self._add_routing_entries(ethernet_chip, tree)

        return self._routing_tables, self._key_to_destination_map

    def _generate_routing_tree(self, ethernet_chip):
        """
        Generates a map for each chip to over which link it gets its data.

        :param ethernet_chip:
        :return: Map of chip.x, chip.y tp (source.x, source.y, source.link)
        :rtype: dict(int.int) = (int, int, int)
        """
        eth_x = ethernet_chip.x
        eth_y = ethernet_chip.y
        tree = dict()
        to_reach = set(
            self._machine.get_existing_xys_by_ethernet(eth_x, eth_y))
        reached = set()
        reached.add((eth_x, eth_y))
        to_reach.remove((eth_x, eth_y))
        found = set()
        found.add((eth_x, eth_y))
        while len(to_reach) > 0:
            just_reached = found
            found = set()
            for x, y in just_reached:
                # Check links starting with the most direct from 0,0
                for link_id in [1, 0, 2, 5, 3, 4]:
                    # Get protential destination
                    destination = self._machine.xy_over_link(x, y, link_id)
                    # If it is useful
                    if destination in to_reach:
                        # check it actually exits
                        if self._machine.is_link_at(x, y, link_id):
                            # Add to tree and record chip reachable
                            tree[destination] = (x, y, link_id)
                            to_reach.remove(destination)
                            found.add(destination)
            if len(found) == 0:
                raise PacmanRoutingException(
                    "Unable to do data in routing on {}.".format(
                        ethernet_chip.ip_address))
        return tree

    def _add_routing_entry(self, x, y, key, processor_id=None, link_id=None):
        """
        Adds a routing entry on this chip. Creating the table if needed

        :param x: chip.x
        :param y: chip.y
        :param key: The key to use
        :param processor_id: placement.p of the monitor vertex if applicable
        :param link_id: If of the link out if applicable
        """
        table = self._routing_tables.get_routing_table_for_chip(x, y)
        if table is None:
            table = MulticastRoutingTable(x, y)
            self._routing_tables.add_routing_table(table)
        if processor_id is None:
            processor_ids = []
        else:
            processor_ids = [processor_id]
        if link_id is None:
            link_ids = []
        else:
            link_ids = [link_id]
        entry = MulticastRoutingEntry(
            routing_entry_key=key, mask=ROUTING_MASK,
            processor_ids=processor_ids, link_ids=link_ids, defaultable=False)
        table.add_multicast_routing_entry(entry)

    def _add_routing_entries(self, ethernet_chip, tree):
        """
        Adds the routing entires based on the tree.

        For every chip with this ethernet:
            - A key is generated (and saved) for this chip.
            - A local route to the monitor core is added.
            - The tree is walked adding a route on each source to get here

        :param ethernet_chip:
        :param tree:
        :return:
        """
        eth_x = ethernet_chip.x
        eth_y = ethernet_chip.y
        key = KEY_START_VALUE
        for (x, y) in self._machine.get_existing_xys_by_ethernet(
                eth_x, eth_y):
            self._key_to_destination_map[x, y] = key
            placement = self._placements.get_placement_of_vertex(
                self._monitors[x, y])
            self._add_routing_entry(x, y, key, processor_id=placement.p)
            while (x, y) in tree:
                x, y, link = tree[(x, y)]
                self._add_routing_entry(x, y, key, link_id=link)
            key += N_KEYS_PER_PARTITION_ID
