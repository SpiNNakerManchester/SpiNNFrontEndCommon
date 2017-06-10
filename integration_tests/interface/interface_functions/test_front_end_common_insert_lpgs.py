from pacman.model.graphs.application import ApplicationGraph, ApplicationVertex
from pacman.model.graphs.common.graph_mapper import GraphMapper
from pacman.model.graphs.machine import MachineGraph
from spinn_front_end_common.interface.interface_functions.\
    front_end_common_insert_live_packet_gatherers_to_graphs import \
    FrontEndCommonInsertLivePacketGatherersToGraphs
from spinn_front_end_common.utilities.utility_objs. \
    live_packet_gather_parameters import \
    LivePacketGatherParameters
from spinn_machine.virtual_machine import VirtualMachine
from spinnman.messages.eieio.eieio_type import EIEIOType

import unittest


class TestInsertLPGs(unittest.TestCase):
    """ tests the LPG insert functions

    """

    def test_that_3_lpgs_are_generated_on_3_board(self):
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
            'tag': None,
            'label': "test"}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        extended = dict(default_params)
        extended.update({'partition_id': "EVENTS"})
        default_params_holder = LivePacketGatherParameters(**extended)
        live_packet_gatherers[default_params_holder] = list()

        # run edge inserter that should go boom
        edge_inserter = FrontEndCommonInsertLivePacketGatherersToGraphs()
        lpg_verts_mapping = edge_inserter(
            live_packet_gatherer_parameters=live_packet_gatherers,
            machine=machine, machine_graph=graph, application_graph=None,
            graph_mapper=None)

        self.assertEqual(len(lpg_verts_mapping[default_params_holder]), 3)
        locs = list()
        locs.append((0, 0))
        locs.append((4, 8))
        locs.append((8, 4))
        for vertex in lpg_verts_mapping[default_params_holder].itervalues():
            x = list(vertex.constraints)[0].x
            y = list(vertex.constraints)[0].y
            key = (x, y)
            locs.remove(key)

        self.assertEqual(len(locs), 0)

        verts = lpg_verts_mapping[default_params_holder].values()
        for vertex in graph.vertices:
            self.assertIn(vertex, verts)

    def test_that_3_lpgs_are_generated_on_3_board_app_graph(self):
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
            'tag': None,
            'label': "test"}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        extended = dict(default_params)
        extended.update({'partition_id': "EVENTS"})
        default_params_holder = LivePacketGatherParameters(**extended)
        live_packet_gatherers[default_params_holder] = list()

        # run edge inserter that should go boom
        edge_inserter = FrontEndCommonInsertLivePacketGatherersToGraphs()
        lpg_verts_mapping = edge_inserter(
            live_packet_gatherer_parameters=live_packet_gatherers,
            machine=machine, machine_graph=graph, application_graph=app_graph,
            graph_mapper=app_graph_mapper)

        self.assertEqual(len(lpg_verts_mapping[default_params_holder]), 3)
        locs = list()
        locs.append((0, 0))
        locs.append((4, 8))
        locs.append((8, 4))
        for vertex in lpg_verts_mapping[default_params_holder].itervalues():
            x = list(vertex.constraints)[0].x
            y = list(vertex.constraints)[0].y
            key = (x, y)
            locs.remove(key)

        self.assertEqual(len(locs), 0)

        verts = lpg_verts_mapping[default_params_holder].values()
        for vertex in graph.vertices:
            self.assertIn(vertex, verts)

        app_verts = set()
        for vertex in lpg_verts_mapping[default_params_holder].itervalues():
            app_vertex = app_graph_mapper.get_application_vertex(vertex)
            self.assertNotEqual(app_vertex, None)
            self.assertIsInstance(app_vertex, ApplicationVertex)
            app_verts.add(app_vertex)
        self.assertEqual(len(app_verts), 3)

    def test_that_6_lpgs_are_generated_2_on_each_eth_chip(self):
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
            'tag': None,
            'label': "test"}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        extended = dict(default_params)
        extended.update({'partition_id': "EVENTS"})
        default_params_holder = LivePacketGatherParameters(**extended)
        live_packet_gatherers[default_params_holder] = list()

        # and special LPG on Ethernet connected chips
        index = 1
        chip_special = dict()
        for chip in machine.ethernet_connected_chips:
            extended['label'] = "test{}".format(index)
            extended['board_address'] = chip.ip_address
            default_params_holder2 = LivePacketGatherParameters(**extended)
            live_packet_gatherers[default_params_holder2] = list()
            chip_special[(chip.x, chip.y)] = default_params_holder2

        # run edge inserter that should go boom
        edge_inserter = FrontEndCommonInsertLivePacketGatherersToGraphs()
        lpg_verts_mapping = edge_inserter(
            live_packet_gatherer_parameters=live_packet_gatherers,
            machine=machine, machine_graph=graph, application_graph=None,
            graph_mapper=None)

        self.assertEqual(len(lpg_verts_mapping[default_params_holder]), 3)

        for eth_chip in chip_special:
            params = chip_special[eth_chip]
            self.assertEqual(len(lpg_verts_mapping[params]), 1)
            vertex = lpg_verts_mapping[params][eth_chip]
            self.assertEqual(eth_chip[0], list(vertex.constraints)[0].x)
            self.assertEqual(eth_chip[1], list(vertex.constraints)[0].y)

    def test_that_6_lpgs_are_generated_2_on_each_eth_chip_app_graph(self):
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
            'tag': None,
            'label': "test"}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        extended = dict(default_params)
        extended.update({'partition_id': "EVENTS"})
        default_params_holder = LivePacketGatherParameters(**extended)
        live_packet_gatherers[default_params_holder] = list()

        # and special LPG on Ethernet connected chips
        index = 1
        chip_special = dict()
        for chip in machine.ethernet_connected_chips:
            extended['label'] = "test{}".format(index)
            extended['board_address'] = chip.ip_address
            default_params_holder2 = LivePacketGatherParameters(**extended)
            live_packet_gatherers[default_params_holder2] = list()
            chip_special[(chip.x, chip.y)] = default_params_holder2

        # run edge inserter that should go boom
        edge_inserter = FrontEndCommonInsertLivePacketGatherersToGraphs()
        lpg_verts_mapping = edge_inserter(
            live_packet_gatherer_parameters=live_packet_gatherers,
            machine=machine, machine_graph=graph, application_graph=app_graph,
            graph_mapper=app_graph_mapper)

        self.assertEqual(len(lpg_verts_mapping[default_params_holder]), 3)

        for eth_chip in chip_special:
            params = chip_special[eth_chip]
            self.assertEqual(len(lpg_verts_mapping[params]), 1)
            vertex = lpg_verts_mapping[params][eth_chip]
            self.assertEqual(eth_chip[0], list(vertex.constraints)[0].x)
            self.assertEqual(eth_chip[1], list(vertex.constraints)[0].y)

        verts = list(lpg_verts_mapping[default_params_holder].values())
        for params in chip_special.values():
            verts.extend(lpg_verts_mapping[params].values())

        for vertex in graph.vertices:
            self.assertIn(vertex, verts)

        app_verts = set()
        for vertex in verts:
            app_vertex = app_graph_mapper.get_application_vertex(vertex)
            self.assertNotEqual(app_vertex, None)
            self.assertIsInstance(app_vertex, ApplicationVertex)
            app_verts.add(app_vertex)
        self.assertEqual(len(app_verts), 6)


if __name__ == "__main__":
    unittest.main()
