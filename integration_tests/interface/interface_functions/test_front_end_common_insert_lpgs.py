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


class TestInsertLPGs(object):
    """ tests the interaction of the LPG inserters

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
            'label': "bupkis"}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        extended = dict(default_params)
        extended.update({'partition_id': "EVENTS"})
        default_params_holder = LivePacketGatherParameters(**extended)
        live_packet_gatherers[default_params_holder] = list()

        # run edge inserter that should go boom
        edge_inserter = FrontEndCommonInsertLivePacketGatherersToGraphs()
        lpg_verts_mapping = edge_inserter(
            live_packet_gatherers=live_packet_gatherers,
            machine=machine, machine_graph=graph, application_graph=None,
            graph_mapper=None)

        if len(lpg_verts_mapping[default_params_holder]) != 3:
            raise Exception
        locs = list()
        locs.append((0, 0))
        locs.append((4, 8))
        locs.append((8, 4))
        for vertex in lpg_verts_mapping[default_params_holder]:
            x = list(vertex.constraints)[0].x
            y = list(vertex.constraints)[0].y
            key = (x, y)
            locs.remove(key)

        if len(locs) != 0:
            raise Exception

        verts = lpg_verts_mapping[default_params_holder]
        for vertex in graph.vertices:
            verts.remove(vertex)
        if len(verts) != 0:
            raise Exception

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
            'label': "bupkis"}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        extended = dict(default_params)
        extended.update({'partition_id': "EVENTS"})
        default_params_holder = LivePacketGatherParameters(**extended)
        live_packet_gatherers[default_params_holder] = list()

        # run edge inserter that should go boom
        edge_inserter = FrontEndCommonInsertLivePacketGatherersToGraphs()
        lpg_verts_mapping = edge_inserter(
            live_packet_gatherers=live_packet_gatherers,
            machine=machine, machine_graph=graph, application_graph=app_graph,
            graph_mapper=app_graph_mapper)

        if len(lpg_verts_mapping[default_params_holder]) != 3:
            raise Exception
        locs = list()
        locs.append((0, 0))
        locs.append((4, 8))
        locs.append((8, 4))
        for vertex in lpg_verts_mapping[default_params_holder]:
            x = list(vertex.constraints)[0].x
            y = list(vertex.constraints)[0].y
            key = (x, y)
            locs.remove(key)

        if len(locs) != 0:
            raise Exception

        verts = list(lpg_verts_mapping[default_params_holder])
        for vertex in graph.vertices:
            verts.remove(vertex)
        if len(verts) != 0:
            raise Exception

        app_verts = set()
        for vertex in lpg_verts_mapping[default_params_holder]:
            app_vertex = app_graph_mapper.get_application_vertex(vertex)
            if not isinstance(app_vertex, ApplicationVertex):
                raise Exception
            if app_vertex is None:
                raise Exception
            app_verts.add(app_vertex)
        if len(app_verts) != 3:
            raise Exception

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
            'label': "bupkis"}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        extended = dict(default_params)
        extended.update({'partition_id': "EVENTS"})
        default_params_holder = LivePacketGatherParameters(**extended)
        live_packet_gatherers[default_params_holder] = list()

        # and special LPG on ethernet connected chips
        index = 1
        chip_special = dict()
        for chip in machine.ethernet_connected_chips:
            extended['label'] = "bupkis{}".format(index)
            extended['board_address'] = chip.ip_address
            default_params_holder2 = LivePacketGatherParameters(**extended)
            live_packet_gatherers[default_params_holder2] = list()
            chip_special[(chip.x, chip.y)] = default_params_holder2

        # run edge inserter that should go boom
        edge_inserter = FrontEndCommonInsertLivePacketGatherersToGraphs()
        lpg_verts_mapping = edge_inserter(
            live_packet_gatherers=live_packet_gatherers,
            machine=machine, machine_graph=graph, application_graph=None,
            graph_mapper=None)

        if len(lpg_verts_mapping[default_params_holder]) != 3:
            raise Exception
        locs = list()
        locs.append((0, 0))
        locs.append((4, 8))
        locs.append((8, 4))
        for vertex in lpg_verts_mapping[default_params_holder]:
            locs.remove((list(vertex.constraints)[0].x,
                         list(vertex.constraints)[0].y))

        for eth_chip in chip_special:
            params = chip_special[eth_chip]
            if len(lpg_verts_mapping[params]) != 1:
                raise Exception
            vertex = lpg_verts_mapping[params][0]
            if eth_chip[0] != list(vertex.constraints)[0].x:
                raise Exception
            if eth_chip[1] != list(vertex.constraints)[0].y:
                raise Exception

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
            'label': "bupkis"}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        extended = dict(default_params)
        extended.update({'partition_id': "EVENTS"})
        default_params_holder = LivePacketGatherParameters(**extended)
        live_packet_gatherers[default_params_holder] = list()

        # and special LPG on ethernet connected chips
        index = 1
        chip_special = dict()
        for chip in machine.ethernet_connected_chips:
            extended['label'] = "bupkis{}".format(index)
            extended['board_address'] = chip.ip_address
            default_params_holder2 = LivePacketGatherParameters(**extended)
            live_packet_gatherers[default_params_holder2] = list()
            chip_special[(chip.x, chip.y)] = default_params_holder2

        # run edge inserter that should go boom
        edge_inserter = FrontEndCommonInsertLivePacketGatherersToGraphs()
        lpg_verts_mapping = edge_inserter(
            live_packet_gatherers=live_packet_gatherers,
            machine=machine, machine_graph=graph, application_graph=app_graph,
            graph_mapper=app_graph_mapper)

        if len(lpg_verts_mapping[default_params_holder]) != 3:
            raise Exception
        locs = list()
        locs.append((0, 0))
        locs.append((4, 8))
        locs.append((8, 4))
        for vertex in lpg_verts_mapping[default_params_holder]:
            locs.remove((list(vertex.constraints)[0].x,
                         list(vertex.constraints)[0].y))

        for eth_chip in chip_special:
            params = chip_special[eth_chip]
            if len(lpg_verts_mapping[params]) != 1:
                raise Exception
            vertex = lpg_verts_mapping[params][0]
            if eth_chip[0] != list(vertex.constraints)[0].x:
                raise Exception
            if eth_chip[1] != list(vertex.constraints)[0].y:
                raise Exception

        verts = list(lpg_verts_mapping[default_params_holder])
        for eth_chip in chip_special:
            params = chip_special[eth_chip]
            verts.append(lpg_verts_mapping[params][0])

        verts2 = list(verts)

        for vertex in graph.vertices:
            verts.remove(vertex)
        if len(verts) != 0:
            raise Exception

        app_verts = set()
        for vertex in verts2:
            app_vertex = app_graph_mapper.get_application_vertex(vertex)
            if not isinstance(app_vertex, ApplicationVertex):
                raise Exception
            if app_vertex is None:
                raise Exception
            app_verts.add(app_vertex)
        if len(app_verts) != 6:
            raise Exception


if __name__ == "__main__":
    test = TestInsertLPGs()
    test.test_that_3_lpgs_are_generated_on_3_board()
    test.test_that_6_lpgs_are_generated_2_on_each_eth_chip()
    test.test_that_3_lpgs_are_generated_on_3_board_app_graph()
    test.test_that_6_lpgs_are_generated_2_on_each_eth_chip_app_graph()
