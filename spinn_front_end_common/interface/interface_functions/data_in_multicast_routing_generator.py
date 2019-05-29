from pacman.model.graphs.machine import MachineGraph, MachineEdge
from pacman.model.placements import Placements, Placement
from pacman.model.routing_tables import (
    MulticastRoutingTables, MulticastRoutingTable)
from pacman.operations.fixed_route_router.fixed_route_router import (
    RoutingMachineVertex)
from pacman.operations.router_algorithms import BasicDijkstraRouting
from spinn_machine import (
    Machine, Router, VirtualMachine, MulticastRoutingEntry)
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.utilities.helpful_functions import (
    calculate_board_level_chip_id, calculate_machine_level_chip_id)

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

    def __call__(self, machine, extra_monitor_cores, placements,
                 board_version):
        # pylint: disable=attribute-defined-outside-init
        self._real_machine = machine
        self._real_placements = placements
        self._monitors = extra_monitor_cores
        self._board_version = board_version
        # create progress bar
        progress = ProgressBar(
            machine.ethernet_connected_chips,
            "Generating routing tables for data in system processes")

        # create routing table holder
        routing_tables = MulticastRoutingTables()
        key_to_destination_map = dict()

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
            partitions_in_table = routing_tables_by_partition.\
                get_entries_for_router(fake_chip_x, fake_chip_y)

            real_chip_x, real_chip_y = calculate_machine_level_chip_id(
                fake_chip_x, fake_chip_y, ethernet_chip.x, ethernet_chip.y,
                self._real_machine)

            multicast_routing_table = MulticastRoutingTable(
                real_chip_x, real_chip_y)

            # build routing table entries
            for partition in partitions_in_table:
                entry = partitions_in_table[partition]
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
        down_links = set()
        fake_machine = self._real_machine

        for (chip_x, chip_y) in self._real_machine.get_chips_on_board(
                ethernet_connected_chip):

            # add destination vertex
            vertex = RoutingMachineVertex()
            fake_graph.add_vertex(vertex)

            # adjust for wrap around's
            fake_x, fake_y = calculate_board_level_chip_id(
                chip_x, chip_y, eth_x, eth_y, self._real_machine)

            # locate correct chips extra monitor placement
            placement = self._real_placements.get_placement_of_vertex(
                self._monitors[chip_x, chip_y])

            # build fake placement
            fake_placements.add_placement(Placement(
                x=fake_x, y=fake_y, p=placement.p, vertex=vertex))

            # remove links to ensure it maps on just chips of this board.
            down_links.update({
                (fake_x, fake_y, link)
                for link in range(Router.MAX_LINKS_PER_ROUTER)
                if not self._real_machine.is_link_at(chip_x, chip_y, link)})

        # Create a fake machine consisting of only the one board that
        # the routes should go over
        valid_48_boards = list()
        valid_48_boards.extend(Machine.BOARD_VERSION_FOR_48_CHIPS)
        valid_48_boards.append(None)

        if (self._board_version in valid_48_boards and (
                self._real_machine.max_chip_x > MAX_CHIP_X or
                self._real_machine.max_chip_y > MAX_CHIP_Y)):
            down_chips = {
                (x, y) for x, y in zip(
                    range(Machine.SIZE_X_OF_ONE_BOARD),
                    range(Machine.SIZE_Y_OF_ONE_BOARD))
                if not self._real_machine.is_chip_at(
                    (x + eth_x) % (self._real_machine.max_chip_x + 1),
                    (y + eth_y) % (self._real_machine.max_chip_y + 1))}

            # build a fake machine which is just one board but with the
            # missing bits of the real board
            fake_machine = VirtualMachine(
                Machine.SIZE_X_OF_ONE_BOARD, Machine.SIZE_Y_OF_ONE_BOARD,
                False, down_chips=down_chips, down_links=down_links)

        # build source
        destination_vertices = fake_graph.vertices
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
        for vertex in destination_vertices:
            if vertex != vertex_source:
                fake_graph.add_edge(
                    MachineEdge(pre_vertex=vertex_source, post_vertex=vertex),
                    counter)
                fake_placement = fake_placements.get_placement_of_vertex(
                    vertex)

                # adjust to real chip ids
                real_chip_xy = calculate_machine_level_chip_id(
                    fake_placement.x, fake_placement.y,
                    ethernet_connected_chip.x, ethernet_connected_chip.y,
                    self._real_machine)
                destination_to_partition_id_map[real_chip_xy] = \
                    counter
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
