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
from typing import Dict, List, Tuple, Set, Optional, cast

from spinn_utilities.log import FormatAdapter
from spinn_utilities.typing.coords import XY
from spinn_utilities.progress_bar import ProgressBar

from spinn_machine import Chip, MulticastRoutingEntry, RoutingEntry

from pacman.exceptions import (PacmanRoutingException)
from pacman.model.routing_tables import (
    MulticastRoutingTables, UnCompressedMulticastRoutingTable)

from spinn_front_end_common.data import FecDataView

# ADDRESS_KEY, DATA_KEY, BOUNDARY_KEY
N_KEYS_PER_PARTITION_ID = 8
# timeout key, timeout emergency key, clear reinjection queue.
N_KEYS_PER_REINJECTION_PARTITION = 3
KEY_START_VALUE = 8
ROUTING_MASK = 0xFFFFFFF8

logger = FormatAdapter(logging.getLogger(__name__))


def system_multicast_routing_generator() -> Tuple[
        MulticastRoutingTables, Dict[XY, int], Dict[XY, int]]:
    """
    Generates routing table entries used by the data-in processes with the
    extra monitor cores.

    :return: routing tables, destination-to-key map,
        board-location-to-timeout-key map
    """
    return _SystemMulticastRoutingGenerator().generate_system_routes()


class _SystemMulticastRoutingGenerator(object):
    """
    Generates routing table entries used by the data in processes with the
    extra monitor cores.
    """
    __slots__ = (
        "_key_to_destination_map",
        "_machine",
        "_routing_tables",
        "_time_out_keys_by_board")

    def __init__(self) -> None:
        self._machine = FecDataView.get_machine()
        self._routing_tables = MulticastRoutingTables()
        self._key_to_destination_map: Dict[XY, int] = dict()
        self._time_out_keys_by_board: Dict[XY, int] = dict()

    def generate_system_routes(self) -> Tuple[
            MulticastRoutingTables, Dict[XY, int], Dict[XY, int]]:
        """
        :return: routing tables, destination-to-key map,
            board-location-to-timeout-key map
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

    __LINK_ORDER = (1, 0, 2, 5, 3, 4)

    def _generate_routing_tree(self, ethernet_chip: Chip) -> Optional[
            Dict[Chip, Tuple[Chip, int]]]:
        """
        Generates a map for each chip to over which link it gets its data.

        :param ethernet_chip:
        :return: Map of chip to (source_chip, source_link)
        """
        tree: Dict[Chip, Tuple[Chip, int]] = dict()
        to_reach = set(self._machine.get_chips_by_ethernet(
            ethernet_chip.x, ethernet_chip.y))
        to_reach.remove(ethernet_chip)
        found = {ethernet_chip}
        while to_reach:
            just_reached: Set[Chip]
            just_reached, found = found, set()
            for chip in just_reached:
                # Check links starting with the most direct from 0,0
                for link_id in self.__LINK_ORDER:
                    # Get potential destination
                    destination = self._machine.get_chip_at(
                        *self._machine.xy_over_link(
                            chip.x, chip.y, link_id))
                    # If destination is useful and link exists
                    if destination in to_reach and (
                            chip.router.is_link(link_id)):
                        # Add to tree and record chip reachable
                        tree[destination] = (chip, link_id)
                        to_reach.remove(destination)
                        found.add(destination)
            if not found:
                return None
        return tree

    def _logging_retry(
            self, ethernet_chip: Chip) -> Dict[Chip, Tuple[Chip, int]]:
        tree: Dict[Chip, Tuple[Chip, int]] = dict()
        to_reach = set(self._machine.get_chips_by_ethernet(
            ethernet_chip.x, ethernet_chip.y))
        to_reach.remove(ethernet_chip)
        found = {ethernet_chip}
        logger.warning("In _logging_retry")
        for chip in to_reach:
            logger.warning("Still need to reach {}:{}", chip.x, chip.y)
        while to_reach:
            just_reached, found = found, set()
            for chip in just_reached:
                logger.warning("Trying from {}:{}", chip.x, chip.y)
                # Check links starting with the most direct from 0,0
                for link_id in self.__LINK_ORDER:
                    # Get potential destination
                    destination = self._machine.get_chip_at(
                        *self._machine.xy_over_link(
                            chip.x, chip.y, link_id))
                    # If it is useful
                    if destination and destination in to_reach:
                        logger.warning(
                            "Could reach ({},{}) over {}",
                            destination.x, destination.y, link_id)
                        # check it actually exits
                        if chip.router.is_link(link_id):
                            # Add to tree and record chip reachable
                            tree[destination] = (chip, link_id)
                            to_reach.remove(destination)
                            found.add(destination)
                        else:
                            logger.error("Link down")
            logger.warning("Found {}", len(found))
            if not found:
                raise PacmanRoutingException(
                    "Unable to do data in routing on "
                    f"{ethernet_chip.ip_address}.")
        return tree

    def _add_routing_entry(
            self, chip: Chip, key: int, *, processor_id: Optional[int] = None,
            link_ids: Optional[List[int]] = None) -> None:
        """
        Adds a routing entry on this chip, creating the table if needed.

        :param chip: The chip
        :param key: The key to use
        :param processor_id: placement.p of the monitor vertex if applicable
        """
        table = cast(
            Optional[UnCompressedMulticastRoutingTable],
            self._routing_tables.get_routing_table_for_chip(chip.x, chip.y))
        if table is None:
            table = UnCompressedMulticastRoutingTable(chip.x, chip.y)
            self._routing_tables.add_routing_table(table)
        if processor_id is None:
            processor_ids = []
        else:
            processor_ids = [processor_id]
        if link_ids is None:
            link_ids = []
        routing_entry = RoutingEntry(
            processor_ids=processor_ids, link_ids=link_ids)
        entry = MulticastRoutingEntry(
            key=key, mask=ROUTING_MASK,
            routing_entry=routing_entry)
        table.add_multicast_routing_entry(entry)

    def _add_routing_entries(self, ethernet_chip: Chip,
                             tree: Dict[Chip, Tuple[Chip, int]]) -> None:
        """
        Adds the routing entries based on the tree.

        For every chip with this Ethernet-enabled chip on the board:
            - A key is generated (and saved) for this chip.
            - A local route to the monitor core is added.
            - The tree is walked adding a route on each source to get here

        :param ethernet_chip: the Ethernet-enabled chip to make entries for
        :param tree: map of chips and links
        """
        eth_x, eth_y = ethernet_chip.x, ethernet_chip.y
        key = KEY_START_VALUE
        for chip in self._machine.get_chips_by_ethernet(eth_x, eth_y):
            self._key_to_destination_map[chip.x, chip.y] = key
            placement = FecDataView.get_placement_of_vertex(
                FecDataView.get_monitor_by_chip(chip))
            self._add_routing_entry(chip, key, processor_id=placement.p)
            while chip in tree:
                chip, link = tree[chip]
                self._add_routing_entry(chip, key, link_ids=[link])
            key += N_KEYS_PER_PARTITION_ID

        # accumulate links to make a broadcast
        links_per_chip = defaultdict(list)
        for chip_key in tree:
            chip, link = tree[chip_key]
            links_per_chip[chip].append(link)

        # add broadcast router timeout keys
        time_out_key = key
        for chip in self._machine.get_chips_by_ethernet(eth_x, eth_y):
            placement = FecDataView.get_placement_of_vertex(
                FecDataView.get_monitor_by_chip(chip))
            self._add_routing_entry(
                chip, time_out_key, processor_id=placement.p,
                link_ids=links_per_chip[chip])
            # update tracker
            self._time_out_keys_by_board[eth_x, eth_y] = key
