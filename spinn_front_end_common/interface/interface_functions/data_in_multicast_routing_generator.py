from pacman.model.graphs.machine import MachineGraph, MachineEdge
from pacman.model.placements import Placements, Placement
from pacman.model.routing_tables import MulticastRoutingTables, \
    MulticastRoutingTable
from pacman.operations.fixed_route_router.fixed_route_router import \
    RoutingMachineVertex
from pacman.operations.router_algorithms import BasicDijkstraRouting
from spinn_machine import Router, VirtualMachine, MulticastRoutingEntry
from spinn_utilities.progress_bar import ProgressBar


class DataInMulticastRoutingGenerator(object):
    """ generates routing table entries used by the data in processes with the\
    extra monitor cores. 
    """

    RANDOM_PROCESSOR = 4
    FAKE_ETHERNET_CHIP_X = 0
    FAKE_ETHERNET_CHIP_Y = 0
    ROUTING_MASK = 0xFFFFFFFF

    def __call__(self, machine, extra_monitor_cores, placements,
                 board_version):

        # create progress bar
        progress = ProgressBar(
            machine.ethernet_connected_chips,
            "Generating routing tables for data in system processes")

        # create routing table holder
        routing_tables = MulticastRoutingTables()
        key_to_destination_map = None

        for ethernet_chip in progress.over(machine.ethernet_connected_chips):
            fake_graph, fake_placements, fake_machine, \
                key_to_destination_map = self._create_fake_network(
                    ethernet_chip, machine, extra_monitor_cores, placements,
                    board_version)
            routing_tables_by_partition = self.do_routing(
                fake_graph=fake_graph, fake_placements=fake_placements,
                fake_machine=fake_machine)
            self._generate_routing_tables(
                routing_tables, routing_tables_by_partition)
        return routing_tables, key_to_destination_map

    @staticmethod
    def _generate_routing_tables(routing_tables, routing_tables_by_partition):
        """ from the routing. use the partition id as key, and build mc\
         routing tables
        
        :param routing_tables: the routing tables to store routing tables in
        :param routing_tables_by_partition: the routing output
        :return: dict of chip x and chip yto key to get there
        :rtype: dict
        """
        key_to_destination_map = dict()
        for chip_x, chip_y in routing_tables_by_partition.get_routers():
            partitions_in_table = routing_tables_by_partition.\
                get_entries_for_router(chip_x, chip_y)
            multicast_routing_table = MulticastRoutingTable(chip_x, chip_y)
            for partition in partitions_in_table:

                # build routing table entries
                entry = partitions_in_table[partition]
                multicast_routing_table.add_multicast_routing_entry(
                    MulticastRoutingEntry(
                        routing_entry_key=partition.identifier,
                        mask=DataInMulticastRoutingGenerator.ROUTING_MASK,
                        processor_ids=entry.out_going_processors,
                        link_ids=entry.out_going_links,
                        defaultable=entry.defaultable))

            # add routing table to pile
            routing_tables.add_routing_table(multicast_routing_table)

    def _create_fake_network(
            self, ethernet_connected_chip, machine, extra_monitor_cores,
            placements, board_version):
        """ generate the fake network for each board
        
        :param ethernet_connected_chip: the ethernet chip to fire from
        :param machine: the real SpiNNMachine instance
        :param extra_monitor_cores: the extra monitor cores
        :param placements: the real placements instance
        :param board_version: the board version
        :return: fake graph, fake placements, fake machine.
        """

        fake_graph = MachineGraph(label="routing fake_graph")
        fake_placements = Placements()
        destination_to_partition_identifer_map = dict()

        # build fake setup for the routing
        eth_x = ethernet_connected_chip.x
        eth_y = ethernet_connected_chip.y
        down_links = set()
        fake_machine = machine

        for (chip_x, chip_y) in machine.get_chips_on_board(
                ethernet_connected_chip):

            # add destination vertex
            vertex = RoutingMachineVertex()
            fake_graph.add_vertex(vertex)

            # adjust for wrap around's
            rel_x = chip_x - eth_x
            if rel_x < 0:
                rel_x += machine.max_chip_x + 1
            rel_y = chip_y - eth_y
            if rel_y < 0:
                rel_y += machine.max_chip_y + 1

            # locate correct chips extra monitor placement
            placement = placements.get_placement_of_vertex(
                extra_monitor_cores[chip_x, chip_y])

            # build fake placement
            fake_placements.add_placement(Placement(
                    x=rel_x, y=rel_y, p=placement.p, vertex=vertex))

            # remove links to ensure it maps on just chips of this board.
            down_links.update({
                (rel_x, rel_y, link) for link in
            range(Router.MAX_LINKS_PER_ROUTER)
                if not machine.is_link_at(chip_x, chip_y, link)})

            # Create a fake machine consisting of only the one board that
            # the routes should go over
            if (board_version in machine.BOARD_VERSION_FOR_48_CHIPS and
                    (machine.max_chip_x > machine.MAX_CHIP_X_ID_ON_ONE_BOARD or
                     machine.max_chip_y > machine.MAX_CHIP_Y_ID_ON_ONE_BOARD)):
                down_chips = {
                    (x, y) for x, y in zip(
                        range(machine.SIZE_X_OF_ONE_BOARD),
                        range(machine.SIZE_Y_OF_ONE_BOARD))
                    if not machine.is_chip_at(
                        (x + eth_x) % (machine.max_chip_x + 1),
                        (y + eth_y) % (machine.max_chip_y + 1))}

                # build a fake machine which is just one board but with the
                # missing bits of the real board
                fake_machine = VirtualMachine(
                    machine.SIZE_X_OF_ONE_BOARD, machine.SIZE_Y_OF_ONE_BOARD,
                    False, down_chips=down_chips, down_links=down_links)

        # build source
        destination_vertices = fake_graph.vertices
        vertex_source = RoutingMachineVertex()
        fake_graph.add_vertex(vertex_source)

        fake_placements.add_placement(Placement(
            x=self.FAKE_ETHERNET_CHIP_X, y=self.FAKE_ETHERNET_CHIP_Y,
            p=self.RANDOM_PROCESSOR, vertex=vertex_source))

        # deal with edges, each one being in a unique partition id, to
        # allow unique routing to each chip.
        counter = 1
        for vertex in destination_vertices:
            fake_graph.add_edge(
                MachineEdge(pre_vertex=vertex_source, post_vertex=vertex),
                counter)
            fake_placement = fake_placements.get_placement_of_vertex(vertex)
            destination_to_partition_identifer_map[
                fake_placement.x, fake_placement.y] = counter
            counter += 1

        return (fake_graph, fake_placements, fake_machine,
                destination_to_partition_identifer_map)

    @staticmethod
    def do_routing(fake_placements, fake_graph, fake_machine):
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
