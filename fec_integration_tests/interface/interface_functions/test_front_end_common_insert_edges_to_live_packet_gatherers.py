from pacman.model.graphs.application import ApplicationGraph
from pacman.model.graphs.common import GraphMapper, Slice
from pacman.model.graphs.machine import MachineGraph, SimpleMachineVertex
from pacman.model.placements import Placements, Placement
from pacman.model.resources import ResourceContainer
from spinn_front_end_common.interface.interface_functions import \
    InsertEdgesToLivePacketGatherers
from spinn_front_end_common.utilities.utility_objs import \
    LivePacketGatherParameters
from spinn_front_end_common.utility_models \
    import LivePacketGather, LivePacketGatherMachineVertex
from spinn_machine import VirtualMachine
from spinnman.messages.eieio import EIEIOType
from fec_integration_tests.interface.interface_functions.test_vertex import \
    TestVertex

import unittest
from collections import defaultdict


class TestInsertLPGEdges(unittest.TestCase):
    """ tests the interaction of the EDGE INSERTION OF LPGS
    """

    def test_local_verts_go_to_local_lpgs(self):
        machine = VirtualMachine(width=12, height=12, with_wrap_arounds=True)
        graph = MachineGraph("Test")

        default_params = {
            'use_prefix': False,
            'key_prefix': None,
            'prefix_type': None,
            'message_type': EIEIOType.KEY_32_BIT,
            'right_shift': 0,
            'payload_as_time_stamps': True,
            'use_payload_prefix': True,
            'payload_prefix': None,
            'payload_right_shift': 0,
            'number_of_packets_sent_per_time_step': 0,
            'hostname': None,
            'port': None,
            'strip_sdp': None,
            'board_address': None,
            'tag': None}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        extended = dict(default_params)
        extended.update({'partition_id': "EVENTS"})
        default_params_holder = LivePacketGatherParameters(**extended)
        live_packet_gatherers[default_params_holder] = list()

        live_packet_gatherers_to_vertex_mapping = dict()
        live_packet_gatherers_to_vertex_mapping[default_params_holder] = dict()

        placements = Placements()

        # add LPG's (1 for each Ethernet connected chip)
        for chip in machine.ethernet_connected_chips:
            extended = dict(default_params)
            extended.update({'label': 'test'})
            vertex = LivePacketGatherMachineVertex(**extended)
            graph.add_vertex(vertex)
            placements.add_placement(
                Placement(x=chip.x, y=chip.y, p=2, vertex=vertex))
            live_packet_gatherers_to_vertex_mapping[
                default_params_holder][chip.x, chip.y] = vertex

        # tracker of wirings
        verts_expected = defaultdict(list)
        positions = list()
        positions.append([0, 0, 0, 0])
        positions.append([4, 4, 0, 0])
        positions.append([1, 1, 0, 0])
        positions.append([2, 2, 0, 0])
        positions.append([8, 4, 8, 4])
        positions.append([11, 4, 8, 4])
        positions.append([4, 11, 4, 8])
        positions.append([4, 8, 4, 8])
        positions.append([0, 11, 8, 4])
        positions.append([11, 11, 4, 8])
        positions.append([8, 8, 4, 8])
        positions.append([4, 0, 0, 0])
        positions.append([7, 7, 0, 0])

        # add graph vertices which reside on areas of the machine to ensure
        #  spread over boards.
        for x, y, eth_x, eth_y in positions:
            vertex = SimpleMachineVertex(resources=ResourceContainer())
            graph.add_vertex(vertex)
            live_packet_gatherers[default_params_holder].append(vertex)
            verts_expected[eth_x, eth_y].append(vertex)
            placements.add_placement(Placement(x=x, y=y, p=5, vertex=vertex))

        # run edge inserter that should go boom
        edge_inserter = InsertEdgesToLivePacketGatherers()
        edge_inserter(
            live_packet_gatherer_parameters=live_packet_gatherers,
            placements=placements,
            live_packet_gatherers_to_vertex_mapping=(
                live_packet_gatherers_to_vertex_mapping),
            machine=machine, machine_graph=graph, application_graph=None,
            graph_mapper=None)

        # verify edges are in the right place
        for chip in machine.ethernet_connected_chips:
            edges = graph.get_edges_ending_at_vertex(
                live_packet_gatherers_to_vertex_mapping[
                    default_params_holder][chip.x, chip.y])
            for edge in edges:
                self.assertIn(edge.pre_vertex, verts_expected[chip.x, chip.y])

    def test_local_verts_when_multiple_lpgs_are_local(self):
        machine = VirtualMachine(width=12, height=12, with_wrap_arounds=True)
        graph = MachineGraph("Test")

        default_params = {
            'use_prefix': False,
            'key_prefix': None,
            'prefix_type': None,
            'message_type': EIEIOType.KEY_32_BIT,
            'right_shift': 0,
            'payload_as_time_stamps': True,
            'use_payload_prefix': True,
            'payload_prefix': None,
            'payload_right_shift': 0,
            'number_of_packets_sent_per_time_step': 0,
            'hostname': None,
            'port': None,
            'strip_sdp': None,
            'board_address': None,
            'tag': None}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        extended = dict(default_params)
        extended.update({'partition_id': "EVENTS"})
        default_params_holder = LivePacketGatherParameters(**extended)
        live_packet_gatherers[default_params_holder] = list()

        live_packet_gatherers_to_vertex_mapping = defaultdict(dict)

        placements = Placements()

        # add LPG's (1 for each Ethernet connected chip)

        specific_data_holders = dict()
        index = 1
        for chip in machine.ethernet_connected_chips:
            extended = dict(default_params)
            extended.update({'label': "test"})
            vertex = LivePacketGatherMachineVertex(**extended)
            graph.add_vertex(vertex)
            placements.add_placement(
                Placement(x=chip.x, y=chip.y, p=2, vertex=vertex))
            live_packet_gatherers_to_vertex_mapping[
                default_params_holder][chip.x, chip.y] = vertex

            # Add another on each chip separately
            index += 1
            extended = dict(default_params)
            extended['board_address'] = chip.ip_address
            extended.update({'partition_id': "EVENTS"})
            default_params_holder2 = LivePacketGatherParameters(**extended)

            extended = dict(default_params)
            extended.update({'label': "test"})
            vertex = LivePacketGatherMachineVertex(**extended)
            specific_data_holders[(chip.x, chip.y)] = default_params_holder2
            placements.add_placement(Placement(
                x=chip.x, y=chip.y, p=3, vertex=vertex))
            graph.add_vertex(vertex)
            live_packet_gatherers_to_vertex_mapping[
                default_params_holder2][chip.x, chip.y] = vertex
            live_packet_gatherers[default_params_holder2] = list()

        # tracker of wirings
        verts_expected = defaultdict(list)

        positions = list()
        positions.append([0, 0, 0, 0, 2, default_params_holder])
        positions.append([4, 4, 0, 0, 2, default_params_holder])
        positions.append(
            [1, 1, 0, 0, 3, specific_data_holders[(0, 0)]])
        positions.append(
            [2, 2, 0, 0, 3, specific_data_holders[(0, 0)]])
        positions.append([8, 4, 8, 4, 2, default_params_holder])
        positions.append([11, 4, 8, 4, 2, default_params_holder])
        positions.append([4, 11, 4, 8, 2, default_params_holder])
        positions.append([4, 8, 4, 8, 2, default_params_holder])
        positions.append([0, 11, 8, 4, 3, specific_data_holders[(8, 4)]])
        positions.append([11, 11, 4, 8, 3, specific_data_holders[(4, 8)]])
        positions.append([8, 8, 4, 8, 3, specific_data_holders[(4, 8)]])
        positions.append([4, 0, 0, 0, 3, specific_data_holders[(0, 0)]])
        positions.append([7, 7, 0, 0, 2, default_params_holder])

        # add graph vertices which reside on areas of the machine to ensure
        #  spread over boards.
        for x, y, eth_x, eth_y, eth_p, params in positions:
            vertex = SimpleMachineVertex(resources=ResourceContainer())
            graph.add_vertex(vertex)
            live_packet_gatherers[params].append(vertex)
            verts_expected[eth_x, eth_y, eth_p].append(vertex)
            placements.add_placement(Placement(x=x, y=y, p=5, vertex=vertex))

        # run edge inserter that should go boom
        edge_inserter = InsertEdgesToLivePacketGatherers()
        edge_inserter(
            live_packet_gatherer_parameters=live_packet_gatherers,
            placements=placements,
            live_packet_gatherers_to_vertex_mapping=(
                live_packet_gatherers_to_vertex_mapping),
            machine=machine, machine_graph=graph, application_graph=None,
            graph_mapper=None)

        # verify edges are in the right place
        for chip in machine.ethernet_connected_chips:
            for params, p in zip(
                    (default_params_holder,
                     specific_data_holders[chip.x, chip.y]),
                    (2, 3)):
                edges = graph.get_edges_ending_at_vertex(
                    live_packet_gatherers_to_vertex_mapping[
                        params][chip.x, chip.y])
                for edge in edges:
                    self.assertIn(
                        edge.pre_vertex, verts_expected[chip.x, chip.y, p])

    def test_local_verts_go_to_local_lpgs_app_graph(self):
        machine = VirtualMachine(width=12, height=12, with_wrap_arounds=True)
        graph = MachineGraph("Test")
        app_graph = ApplicationGraph("Test")
        app_graph_mapper = GraphMapper()

        default_params = {
            'use_prefix': False,
            'key_prefix': None,
            'prefix_type': None,
            'message_type': EIEIOType.KEY_32_BIT,
            'right_shift': 0,
            'payload_as_time_stamps': True,
            'use_payload_prefix': True,
            'payload_prefix': None,
            'payload_right_shift': 0,
            'number_of_packets_sent_per_time_step': 0,
            'hostname': None,
            'port': None,
            'strip_sdp': None,
            'board_address': None,
            'tag': None}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        extended = dict(default_params)
        extended.update({'partition_id': "EVENTS"})
        default_params_holder = LivePacketGatherParameters(**extended)
        live_packet_gatherers[default_params_holder] = list()

        live_packet_gatherers_to_vertex_mapping = defaultdict(dict)

        placements = Placements()

        # add LPG's (1 for each Ethernet connected chip
        for chip in machine.ethernet_connected_chips:
            vertex = LivePacketGather(**default_params)
            app_graph.add_vertex(vertex)
            vertex_slice = Slice(0, 0)
            resources_required = vertex.get_resources_used_by_atoms(
                vertex_slice)
            mac_vertex = vertex.create_machine_vertex(
                vertex_slice, resources_required)
            graph.add_vertex(mac_vertex)
            app_graph_mapper.add_vertex_mapping(
                mac_vertex, Slice(0, 0), vertex)
            placements.add_placement(
                Placement(x=chip.x, y=chip.y, p=2, vertex=mac_vertex))
            live_packet_gatherers_to_vertex_mapping[
                default_params_holder][chip.x, chip.y] = mac_vertex

        # tracker of wirings
        verts_expected = defaultdict(list)

        positions = list()
        positions.append([0, 0, 0, 0])
        positions.append([4, 4, 0, 0])
        positions.append([1, 1, 0, 0])
        positions.append([2, 2, 0, 0])
        positions.append([8, 4, 8, 4])
        positions.append([11, 4, 8, 4])
        positions.append([4, 11, 4, 8])
        positions.append([4, 8, 4, 8])
        positions.append([0, 11, 8, 4])
        positions.append([11, 11, 4, 8])
        positions.append([8, 8, 4, 8])
        positions.append([4, 0, 0, 0])
        positions.append([7, 7, 0, 0])

        # add graph vertices which reside on areas of the machine to ensure
        #  spread over boards.
        for x, y, eth_x, eth_y in positions:
            vertex = TestVertex(1)
            app_graph.add_vertex(vertex)
            vertex_slice = Slice(0, 0)
            resources_required = vertex.get_resources_used_by_atoms(
                vertex_slice)
            mac_vertex = vertex.create_machine_vertex(
                vertex_slice, resources_required)
            graph.add_vertex(mac_vertex)
            app_graph_mapper.add_vertex_mapping(
                mac_vertex, vertex_slice, vertex)
            live_packet_gatherers[default_params_holder].append(vertex)
            verts_expected[eth_x, eth_y].append(mac_vertex)
            placements.add_placement(
                Placement(x=x, y=y, p=5, vertex=mac_vertex))

        # run edge inserter that should go boom
        edge_inserter = InsertEdgesToLivePacketGatherers()
        edge_inserter(
            live_packet_gatherer_parameters=live_packet_gatherers,
            placements=placements,
            live_packet_gatherers_to_vertex_mapping=(
                live_packet_gatherers_to_vertex_mapping),
            machine=machine, machine_graph=graph, application_graph=app_graph,
            graph_mapper=app_graph_mapper)

        # verify edges are in the right place
        for chip in machine.ethernet_connected_chips:
            edges = graph.get_edges_ending_at_vertex(
                live_packet_gatherers_to_vertex_mapping[
                    default_params_holder][chip.x, chip.y])
            for edge in edges:
                self.assertIn(edge.pre_vertex, verts_expected[chip.x, chip.y])

        # check app graph
        for chip in machine.ethernet_connected_chips:
            app_verts_expected = [
                app_graph_mapper.get_application_vertex(vert)
                for vert in verts_expected[chip.x, chip.y]]
            lpg_machine = live_packet_gatherers_to_vertex_mapping[
                default_params_holder][chip.x, chip.y]
            lpg_app = app_graph_mapper.get_application_vertex(lpg_machine)
            edges = app_graph.get_edges_ending_at_vertex(lpg_app)
            for edge in edges:
                self.assertIn(edge.pre_vertex, app_verts_expected)


if __name__ == "__main__":
    unittest.main()
