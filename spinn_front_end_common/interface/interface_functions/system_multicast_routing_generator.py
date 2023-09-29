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
from collections import defaultdict
import logging
from spinn_utilities.log import FormatAdapter
from pacman.exceptions import (PacmanRoutingException)
from pacman.model.routing_tables import (
    MulticastRoutingTables, UnCompressedMulticastRoutingTable)
from spinn_machine import MulticastRoutingEntry
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.data import FecDataView

# ADDRESS_KEY, DATA_KEY, BOUNDARY_KEY
N_KEYS_PER_PARTITION_ID = 8
# timeout key, timeout emergency key, clear reinjection queue.
N_KEYS_PER_REINJECTION_PARTITION = 3
KEY_START_VALUE = 8
ROUTING_MASK = 0xFFFFFFF8

logger = FormatAdapter(logging.getLogger(__name__))


def system_multicast_routing_generator():
    """
    Generates routing table entries used by the data-in processes with the
    extra monitor cores.

    :return: routing tables, destination-to-key map,
        board-location-to-timeout-key map
    :rtype: tuple(~pacman.model.routing_tables.MulticastRoutingTables,
        dict(tuple(int,int),int), dict(tuple(int,int),int))
    """
    generator = _SystemMulticastRoutingGenerator()
    # pylint: disable=protected-access
    return generator._run()


class _SystemMulticastRoutingGenerator(object):
    """
    Generates routing table entries used by the data in processes with the
    extra monitor cores.
    """
    __slots__ = ["_key_to_destination_map", "_machine",
                 "_routing_tables", "_time_out_keys_by_board"]

    def __init__(self):
        """

        :param ~pacman.model.placements.Placements placements:
        """
        self._machine = FecDataView.get_machine()
        self._routing_tables = MulticastRoutingTables()
        self._key_to_destination_map = dict()
        self._time_out_keys_by_board = dict()

    def _run(self):
        """
        :return: routing tables, destination-to-key map,
            board-location-to-timeout-key map
        :rtype: tuple(~pacman.model.routing_tables.MulticastRoutingTables,
            dict(tuple(int,int),int), dict(tuple(int,int),int))
        """
        # create progress bar
        progress = ProgressBar(
            self._machine.ethernet_connected_chips,
            "Generating routing tables for data in system processes")

        for ethernet_chip in progress.over(
                self._machine.ethernet_connected_chips):
            tree = self._generate_routing_tree(ethernet_chip)
            if tree is None:
                tree = self._logging_retry(ethernet_chip)
            self._add_routing_entries(ethernet_chip, tree)

        return (self._routing_tables, self._key_to_destination_map,
                self._time_out_keys_by_board)

    def _generate_routing_tree(self, ethernet_chip):
        """
        Generates a map for each chip to over which link it gets its data.

        :param ~spinn_machine.Chip ethernet_chip:
        :return: Map of chip.x, chip.y to (source.x, source.y, source.link)
        :rtype: dict(tuple(int, int), tuple(int, int, int))
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
                return None
        return tree

    def _logging_retry(self, ethernet_chip):
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
        logger.warning("In _logging_retry")
        for x, y in to_reach:
            logger.warning("Still need to reach {}:{}", x, y)
        while len(to_reach) > 0:
            just_reached = found
            found = set()
            for x, y in just_reached:
                logger.warning("Trying from {}:{}", x, y)
                # Check links starting with the most direct from 0,0
                for link_id in [1, 0, 2, 5, 3, 4]:
                    # Get protential destination
                    destination = self._machine.xy_over_link(x, y, link_id)
                    # If it is useful
                    if destination in to_reach:
                        logger.warning(
                            "Could reach {} over {}", destination, link_id)
                        # check it actually exits
                        if self._machine.is_link_at(x, y, link_id):
                            # Add to tree and record chip reachable
                            tree[destination] = (x, y, link_id)
                            to_reach.remove(destination)
                            found.add(destination)
                        else:
                            logger.error("Link down")
            logger.warning("Found {}", len(found))
            if len(found) == 0:
                raise PacmanRoutingException(
                    "Unable to do data in routing on "
                    f"{ethernet_chip.ip_address}.")
        return tree

    def _add_routing_entry(self, x, y, key, processor_id=None, link_ids=None):
        """
        Adds a routing entry on this chip, creating the table if needed.

        :param int x: chip.x
        :param int y: chip.y
        :param int key: The key to use
        :param int processor_id:
            placement.p of the monitor vertex if applicable
        :param int link_id: If of the link out if applicable
        """
        table = self._routing_tables.get_routing_table_for_chip(x, y)
        if table is None:
            table = UnCompressedMulticastRoutingTable(x, y)
            self._routing_tables.add_routing_table(table)
        if processor_id is None:
            processor_ids = []
        else:
            processor_ids = [processor_id]
        if link_ids is None:
            link_ids = []
        entry = MulticastRoutingEntry(
            routing_entry_key=key, mask=ROUTING_MASK,
            processor_ids=processor_ids, link_ids=link_ids, defaultable=False)
        table.add_multicast_routing_entry(entry)

    def _add_routing_entries(self, ethernet_chip, tree):
        """
        Adds the routing entries based on the tree.

        For every chip with this Ethernet-enabled chip on the board:
            - A key is generated (and saved) for this chip.
            - A local route to the monitor core is added.
            - The tree is walked adding a route on each source to get here

        :param ~spinn_machine.Chip ethernet_chip:
            the Ethernet-enabled chip to make entries for
        :param dict(tuple(int,int),tuple(int,int,int)) tree:
            map of chips and links
        """
        eth_x = ethernet_chip.x
        eth_y = ethernet_chip.y
        key = KEY_START_VALUE
        for (x, y) in self._machine.get_existing_xys_by_ethernet(
                eth_x, eth_y):
            self._key_to_destination_map[x, y] = key
            placement = FecDataView.get_placement_of_vertex(
                FecDataView.get_monitor_by_xy(x, y))
            self._add_routing_entry(x, y, key, processor_id=placement.p)
            while (x, y) in tree:
                x, y, link = tree[(x, y)]
                self._add_routing_entry(x, y, key, link_ids=[link])
            key += N_KEYS_PER_PARTITION_ID

        # accum links to make a broad cast
        links_per_chip = defaultdict(list)
        for chip_key in tree:
            x, y, link = tree[chip_key]
            links_per_chip[x, y].append(link)

        # add broadcast router timeout keys
        time_out_key = key
        for (x, y) in self._machine.get_existing_xys_by_ethernet(
                eth_x, eth_y):
            placement = FecDataView.get_placement_of_vertex(
                FecDataView.get_monitor_by_xy(x, y))
            self._add_routing_entry(
                x, y, time_out_key, processor_id=placement.p,
                link_ids=links_per_chip[x, y])
            # update tracker
            self._time_out_keys_by_board[(eth_x, eth_y)] = key
