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

from six import iteritems
from pacman.exceptions import (
    PacmanAlreadyExistsException, PacmanConfigurationException,
    PacmanRoutingException)
from pacman.model.graphs.machine import MachineGraph, MachineEdge
from pacman.model.placements import Placements, Placement
from pacman.model.routing_tables import (
    MulticastRoutingTables, MulticastRoutingTable)
from pacman.model.graphs.machine import MachineVertex
from pacman.operations.router_algorithms import BasicDijkstraRouting
from spinn_machine import Machine, MulticastRoutingEntry
from spinn_machine import virtual_submachine
from spinn_utilities.progress_bar import ProgressBar

N_KEYS_PER_PARTITION_ID = 4
KEY_START_VALUE = 4
FAKE_ETHERNET_CHIP_X = 0
FAKE_ETHERNET_CHIP_Y = 0
ROUTING_MASK = 0xFFFFFFFC
MAX_CHIP_X = Machine.MAX_CHIP_X_ID_ON_ONE_BOARD
MAX_CHIP_Y = Machine.MAX_CHIP_Y_ID_ON_ONE_BOARD


class DataInMulticastRoutingGenerator(object):
    """ Generates routing table entries used by the data in processes with the\
    extra monitor cores.
    """
    __slots__ = ["_monitors", "_real_machine", "_real_placements","_routing_tables"]

    def __call__(self, machine, extra_monitor_cores, placements):
        # pylint: disable=attribute-defined-outside-init
        self._real_machine = machine
        self._real_placements = placements
        self._monitors = extra_monitor_cores
        # create progress bar
        progress = ProgressBar(
            machine.ethernet_connected_chips,
            "Generating routing tables for data in system processes")

        # create routing table holder
        routing_tables = MulticastRoutingTables()
        self._routing_tables = MulticastRoutingTables()
        key_to_destination_map = dict()

        for ethernet_chip in machine.ethernet_connected_chips:
            tree = self._generate_routing_tree(ethernet_chip)
            self._add_routing_entries(
                ethernet_chip, tree, key_to_destination_map)

        for ethernet_chip in progress.over(machine.ethernet_connected_chips):
            fake_graph, fake_placements, fake_machine, key_to_dest_map = \
                self._create_fake_network(ethernet_chip)

            # update dict for key mapping
            key_to_destination_map.update(key_to_dest_map)

            # do routing
            routing_tables_by_partition = self._do_routing(
                fake_graph=fake_graph, fake_placements=fake_placements,
                fake_machine=fake_machine)
            self._generate_routing_tables(
                routing_tables, routing_tables_by_partition, ethernet_chip)
        return routing_tables, key_to_destination_map

    def _generate_ket_to_destination_map(self, machine):
        key_to_destination_map = dict()
        for ethernet_chip in machine.ethernet_connected_chips:
            eth_x = ethernet_chip.x
            eth_y = ethernet_chip.y
            counter = KEY_START_VALUE
            for chip_xy in self._machine.get_existing_xys_by_ethernet(
                    eth_x, eth_y):
                key_to_destination_map[chip_xy] = counter
                counter += N_KEYS_PER_PARTITION_ID

    def _generate_routing_tree(self, ethernet_chip):
        eth_x = ethernet_chip.x
        eth_y = ethernet_chip.y
        tree = dict()
        to_reach = set(
            self._real_machine.get_existing_xys_by_ethernet(eth_x, eth_y))
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
                    destination = self._real_machine.xy_over_link(x, y, link_id)
                    # If it is useful
                    if destination in to_reach:
                        # check it actually exits
                        if self._real_machine.is_link_at(x, y, link_id):
                            tree[destination] = (x, y, link_id)
                            to_reach.remove(destination)
                            found.add(destination)
                            # build entry and add to table and add to tables
                            key = (x, y)
            if len(found) == 0:
                raise PacmanRoutingException(
                    "Unable to do data in routing on {}.".format(
                        ethernet_chip.ip_address))
        return tree
        for destination, (x, y, link) in iteritems(tree):
            print (destination, x, y, link)
            while (x, y) in tree:
                x, y, link = tree[(x, y)]
                print (destination, x, y, link)

    def _add_routing_entry(self, x, y, key, processor_id=None, link_id=None):


    def _add_routing_entries(
        self, ethernet_chip, tree, key_to_destination_map):
        for ethernet_chip in self._real_machine.ethernet_connected_chips:
            eth_x = ethernet_chip.x
            eth_y = ethernet_chip.y
            counter = KEY_START_VALUE
            for (x, y) in self._machine.get_existing_xys_by_ethernet(
                    eth_x, eth_y):
                key_to_destination_map[x, y] = counter
                counter += N_KEYS_PER_PARTITION_ID
                placement = self._real_placements.get_placement_of_vertex(
                    self._monitors[x, y])
                entry = MulticastRoutingEntry(
                    routing_entry_key=counter, mask=ROUTING_MASK,
                    processor_ids=[placement.p], link_ids=[],
                    defaultable=False)
                multicast_routing_table.add_multicast_routing_entry(entry)
                while (x, y) in tree:
                    x, y, link = tree[(x, y)]
                    print (destination, x, y, link)


    def _generate_routing_tables(
            self, routing_tables, routing_tables_by_partition, ethernet_chip):
        """ from the routing. use the partition id as key, and build mc\
        routing tables.

        :param routing_tables: the routing tables to store routing tables in
        :param routing_tables_by_partition: the routing output
        :param ethernet_chip: the ethernet chip being used
        :return: dict of chip x and chip yto key to get there
        :rtype: dict
        """
        for fake_chip_x, fake_chip_y in \
                routing_tables_by_partition.get_routers():
            multicast_routing_table = MulticastRoutingTable(
                *self._real_machine.get_global_xy(
                    fake_chip_x, fake_chip_y,
                    ethernet_chip.x, ethernet_chip.y))

            # build routing table entries
            for partition, entry in iteritems(
                    routing_tables_by_partition.get_entries_for_router(
                        fake_chip_x, fake_chip_y)):
                multicast_routing_table.add_multicast_routing_entry(
                    MulticastRoutingEntry(
                        routing_entry_key=partition.identifier,
                        mask=ROUTING_MASK, processor_ids=entry.processor_ids,
                        link_ids=entry.link_ids,
                        defaultable=entry.defaultable))

            # add routing table to pile
            routing_tables.add_routing_table(multicast_routing_table)

    def _create_fake_network(self, ethernet_connected_chip):
        """ Generate the fake network for each board

        :param ethernet_connected_chip: the ethernet chip to fire from
        :return: fake graph, fake placements, fake machine.
        """

        fake_graph = MachineGraph(label="routing fake_graph")
        fake_placements = Placements()
        destination_to_partition_id_map = dict()

        # build fake setup for the routing
        eth_x = ethernet_connected_chip.x
        eth_y = ethernet_connected_chip.y
        fake_machine = virtual_submachine(
            self._real_machine, ethernet_connected_chip)

        # Build a fake graph with vertices for all the monitors
        for chip in self._real_machine.get_chips_by_ethernet(eth_x, eth_y):
            # locate correct chips extra monitor placement
            placement = self._real_placements.get_placement_of_vertex(
                self._monitors[chip.x, chip.y])

            # adjust for wrap around's
            fake_x, fake_y = self._real_machine.get_local_xy(chip)

            # add destination vertex
            vertex = RoutingMachineVertex()
            fake_graph.add_vertex(vertex)

            # build fake placement
            fake_placements.add_placement(Placement(
                x=fake_x, y=fake_y, p=placement.p, vertex=vertex))

        # build source vertex, which is for the Gatherer
        vertex_source = RoutingMachineVertex()
        fake_graph.add_vertex(vertex_source)

        for free_processor in range(Machine.MAX_CORES_PER_CHIP):
            if not fake_placements.is_processor_occupied(
                    x=FAKE_ETHERNET_CHIP_X, y=FAKE_ETHERNET_CHIP_Y,
                    p=free_processor):
                fake_placements.add_placement(Placement(
                    x=FAKE_ETHERNET_CHIP_X, y=FAKE_ETHERNET_CHIP_Y,
                    p=free_processor, vertex=vertex_source))
                break

        # deal with edges, each one being in a unique partition id, to
        # allow unique routing to each chip.
        counter = KEY_START_VALUE
        for vertex in fake_graph.vertices:
            if vertex == vertex_source:
                continue
            fake_graph.add_edge(
                MachineEdge(pre_vertex=vertex_source, post_vertex=vertex),
                counter)
            placement = fake_placements.get_placement_of_vertex(vertex)

            # adjust to real chip ids
            real_chip_xy = self._real_machine.get_global_xy(
                placement.x, placement.y, eth_x, eth_y)
            destination_to_partition_id_map[real_chip_xy] = counter
            counter += N_KEYS_PER_PARTITION_ID

        return (fake_graph, fake_placements, fake_machine,
                destination_to_partition_id_map)

    @staticmethod
    def _do_routing(fake_placements, fake_graph, fake_machine):
        """ executes the routing

        :param fake_placements: the fake placements
        :param fake_graph: the fake graph
        :param fake_machine: the fake machine
        :return: the routes
        """
        # route as if using multicast
        router = BasicDijkstraRouting()
        return router(
            placements=fake_placements, machine=fake_machine,
            machine_graph=fake_graph, use_progress_bar=False)


class RoutingMachineVertex(MachineVertex):
    @property
    def resources_required(self):
        return None
