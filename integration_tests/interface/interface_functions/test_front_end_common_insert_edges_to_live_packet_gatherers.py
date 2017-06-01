from pacman.model.graphs.application import ApplicationGraph, ApplicationVertex
from pacman.model.graphs.common.graph_mapper import GraphMapper
from pacman.model.graphs.common.slice import Slice
from pacman.model.graphs.machine import MachineGraph, SimpleMachineVertex, \
    MachineVertex
from pacman.model.placements import Placements, Placement
from pacman.model.resources import ResourceContainer
from spinn_front_end_common.interface.interface_functions.\
    front_end_common_insert_edges_to_live_packet_gatherers import \
    FrontEndCommonInsertEdgesToLivePacketGatherers
from spinn_front_end_common.utilities.utility_objs.\
    live_packet_gather_parameters import \
    LivePacketGatherParameters
from spinn_front_end_common.utility_models.live_packet_gather import \
    LivePacketGather
from spinn_front_end_common.utility_models.\
    live_packet_gather_machine_vertex import \
    LivePacketGatherMachineVertex
from spinn_machine.virtual_machine import VirtualMachine
from spinnman.messages.eieio.eieio_type import EIEIOType
from uinit_test_objects.test_vertex import TestVertex


class TestInsertLPGEdges(object):
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
            'tag': None,
            'label': "bupkis"}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        extended = dict(default_params)
        extended.update({'partition_id': "EVENTS"})
        default_params_holder = LivePacketGatherParameters(**extended)
        live_packet_gatherers[default_params_holder] = list()

        live_packet_gatherers_to_vertex_mapping = dict()
        live_packet_gatherers_to_vertex_mapping[default_params_holder] = list()

        placements = Placements()

        # add LPG's (1 for each ethernet connected chip
        vertex = LivePacketGatherMachineVertex(**default_params)
        graph.add_vertex(vertex)
        placements.add_placement(Placement(x=0, y=0, p=2, vertex=vertex))
        live_packet_gatherers_to_vertex_mapping[
            default_params_holder].append(vertex)

        vertex = LivePacketGatherMachineVertex(**default_params)
        graph.add_vertex(vertex)
        placements.add_placement(Placement(x=4, y=8, p=2, vertex=vertex))
        live_packet_gatherers_to_vertex_mapping[
            default_params_holder].append(vertex)

        vertex = LivePacketGatherMachineVertex(**default_params)
        placements.add_placement(Placement(x=8, y=4, p=2, vertex=vertex))
        graph.add_vertex(vertex)
        live_packet_gatherers_to_vertex_mapping[
            default_params_holder].append(vertex)

        # tracker of wirings
        verts_expected_0_0 = list()
        verts_expected_4_8 = list()
        verts_expected_8_4 = list()

        positions = list()
        positions.append([0, 0, verts_expected_0_0])
        positions.append([4, 4, verts_expected_0_0])
        positions.append([1, 1, verts_expected_0_0])
        positions.append([2, 2, verts_expected_0_0])
        positions.append([8, 4, verts_expected_8_4])
        positions.append([11, 4, verts_expected_8_4])
        positions.append([4, 11, verts_expected_4_8])
        positions.append([4, 8, verts_expected_4_8])
        positions.append([0, 11, verts_expected_8_4])
        positions.append([11, 11, verts_expected_4_8])
        positions.append([8, 8, verts_expected_4_8])
        positions.append([4, 0, verts_expected_0_0])
        positions.append([7, 7, verts_expected_0_0])

        # add graph verts which reside on areas of the machine to ensure
        #  spread over boards.
        for index in range(0, 13):
            vertex = SimpleMachineVertex(resources=ResourceContainer())
            graph.add_vertex(vertex)
            live_packet_gatherers[default_params_holder].append(vertex)
            positions[index][2].append(vertex)
            placements.add_placement(Placement(
                x=positions[index][0], y=positions[index][1], p=5,
                vertex=vertex))

        # run edge inserter that should go boom
        edge_inserter = FrontEndCommonInsertEdgesToLivePacketGatherers()
        edge_inserter(
            live_packet_gatherers=live_packet_gatherers, placements=placements,
            live_packet_recorder_recorded_vertex_type=MachineVertex,
            live_packet_gatherers_to_vertex_mapping=
            live_packet_gatherers_to_vertex_mapping,
            machine=machine, machine_graph=graph, application_graph=None,
            graph_mapper=None)

        # verify edges are in the right place
        # check 0 0 lpg
        edges = graph.get_edges_ending_at_vertex(
            placements.get_vertex_on_processor(0, 0, 2))
        for edge in edges:
            verts_expected_0_0.remove(edge.pre_vertex)
        if len(verts_expected_0_0) != 0:
            raise Exception("wasnt wired correctly")

        # check 4 8 LPG
        edges = graph.get_edges_ending_at_vertex(
            placements.get_vertex_on_processor(4, 8, 2))
        for edge in edges:
            verts_expected_4_8.remove(edge.pre_vertex)
        if len(verts_expected_4_8) != 0:
            raise Exception("wasnt wired correctly")

        # check 4 8 LPG
        edges = graph.get_edges_ending_at_vertex(
            placements.get_vertex_on_processor(8, 4, 2))
        for edge in edges:
            verts_expected_8_4.remove(edge.pre_vertex)
        if len(verts_expected_8_4) != 0:
            raise Exception("wasnt wired correctly")

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
            'tag': None,
            'label': "bupkis"}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        extended = dict(default_params)
        extended.update({'partition_id': "EVENTS"})
        default_params_holder = LivePacketGatherParameters(**extended)
        live_packet_gatherers[default_params_holder] = list()

        live_packet_gatherers_to_vertex_mapping = dict()
        live_packet_gatherers_to_vertex_mapping[default_params_holder] = list()

        placements = Placements()

        # add LPG's (1 for each ethernet connected chip
        vertex = LivePacketGatherMachineVertex(**default_params)
        graph.add_vertex(vertex)
        placements.add_placement(Placement(x=0, y=0, p=2, vertex=vertex))
        live_packet_gatherers_to_vertex_mapping[
            default_params_holder].append(vertex)

        vertex = LivePacketGatherMachineVertex(**default_params)
        graph.add_vertex(vertex)
        placements.add_placement(Placement(x=4, y=8, p=2, vertex=vertex))
        live_packet_gatherers_to_vertex_mapping[
            default_params_holder].append(vertex)

        vertex = LivePacketGatherMachineVertex(**default_params)
        placements.add_placement(Placement(x=8, y=4, p=2, vertex=vertex))
        graph.add_vertex(vertex)
        live_packet_gatherers_to_vertex_mapping[
            default_params_holder].append(vertex)

        # and special LPG on ethernet connected chips
        index = 1
        specific_data_holders = dict()
        for chip in machine.ethernet_connected_chips:
            extended['label'] = "bupkis{}".format(index)
            extended['board_address'] = chip.ip_address
            default_params_holder2 = LivePacketGatherParameters(**extended)
            vertex = LivePacketGatherMachineVertex(**default_params)
            specific_data_holders[(chip.x, chip.y)] = default_params_holder2
            placements.add_placement(Placement(
                x=chip.x, y=chip.y, p=3, vertex=vertex))
            graph.add_vertex(vertex)
            live_packet_gatherers_to_vertex_mapping[default_params_holder2] \
                = list()
            live_packet_gatherers_to_vertex_mapping[
                default_params_holder2].append(vertex)
            live_packet_gatherers[default_params_holder2] = list()

        # tracker of wirings
        verts_expected_0_0_2 = list()
        verts_expected_0_0_3 = list()
        verts_expected_4_8_2 = list()
        verts_expected_4_8_3 = list()
        verts_expected_8_4_2 = list()
        verts_expected_8_4_3 = list()

        positions = list()
        positions.append([0, 0, verts_expected_0_0_2, default_params_holder])
        positions.append([4, 4, verts_expected_0_0_2, default_params_holder])
        positions.append(
            [1, 1, verts_expected_0_0_3, specific_data_holders[(0, 0)]])
        positions.append(
            [2, 2, verts_expected_0_0_3, specific_data_holders[(0, 0)]])
        positions.append([8, 4, verts_expected_8_4_2, default_params_holder])
        positions.append([11, 4, verts_expected_8_4_2, default_params_holder])
        positions.append([4, 11, verts_expected_4_8_2, default_params_holder])
        positions.append([4, 8, verts_expected_4_8_2, default_params_holder])
        positions.append(
            [0, 11, verts_expected_8_4_3, specific_data_holders[(8, 4)]])
        positions.append(
            [11, 11, verts_expected_4_8_3, specific_data_holders[(4, 8)]])
        positions.append(
            [8, 8, verts_expected_4_8_3, specific_data_holders[(4, 8)]])
        positions.append(
            [4, 0, verts_expected_0_0_3, specific_data_holders[(0, 0)]])
        positions.append([7, 7, verts_expected_0_0_2, default_params_holder])

        # add graph verts which reside on areas of the machine to ensure
        #  spread over boards.
        for index in range(0, 13):
            vertex = SimpleMachineVertex(resources=ResourceContainer())
            graph.add_vertex(vertex)
            live_packet_gatherers[positions[index][3]].append(vertex)
            positions[index][2].append(vertex)
            placements.add_placement(Placement(
                x=positions[index][0], y=positions[index][1], p=5,
                vertex=vertex))

        # run edge inserter that should go boom
        edge_inserter = FrontEndCommonInsertEdgesToLivePacketGatherers()
        edge_inserter(
            live_packet_gatherers=live_packet_gatherers, placements=placements,
            live_packet_recorder_recorded_vertex_type=MachineVertex,
            live_packet_gatherers_to_vertex_mapping=
            live_packet_gatherers_to_vertex_mapping,
            machine=machine, machine_graph=graph, application_graph=None,
            graph_mapper=None)

        # verify edges are in the right place
        # check 0 0 lpg
        edges = graph.get_edges_ending_at_vertex(
            placements.get_vertex_on_processor(0, 0, 2))
        for edge in edges:
            verts_expected_0_0_2.remove(edge.pre_vertex)
        if len(verts_expected_0_0_2) != 0:
            raise Exception("wasnt wired correctly")

        edges = graph.get_edges_ending_at_vertex(
            placements.get_vertex_on_processor(0, 0, 3))
        for edge in edges:
            verts_expected_0_0_3.remove(edge.pre_vertex)
        if len(verts_expected_0_0_3) != 0:
            raise Exception("wasnt wired correctly")

        # check 4 8 LPG
        edges = graph.get_edges_ending_at_vertex(
            placements.get_vertex_on_processor(4, 8, 2))
        for edge in edges:
            verts_expected_4_8_2.remove(edge.pre_vertex)
        if len(verts_expected_4_8_2) != 0:
            raise Exception("wasnt wired correctly")

        edges = graph.get_edges_ending_at_vertex(
            placements.get_vertex_on_processor(4, 8, 3))
        for edge in edges:
            verts_expected_4_8_3.remove(edge.pre_vertex)
        if len(verts_expected_4_8_3) != 0:
            raise Exception("wasnt wired correctly")

        # check 4 8 LPG
        edges = graph.get_edges_ending_at_vertex(
            placements.get_vertex_on_processor(8, 4, 2))
        for edge in edges:
            verts_expected_8_4_2.remove(edge.pre_vertex)
        if len(verts_expected_8_4_2) != 0:
            raise Exception("wasnt wired correctly")

        edges = graph.get_edges_ending_at_vertex(
            placements.get_vertex_on_processor(8, 4, 3))
        for edge in edges:
            verts_expected_8_4_3.remove(edge.pre_vertex)
        if len(verts_expected_8_4_3) != 0:
            raise Exception("wasnt wired correctly")

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
            'tag': None,
            'label': "bupkis"}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        extended = dict(default_params)
        extended.update({'partition_id': "EVENTS"})
        default_params_holder = LivePacketGatherParameters(**extended)
        live_packet_gatherers[default_params_holder] = list()

        live_packet_gatherers_to_vertex_mapping = dict()
        live_packet_gatherers_to_vertex_mapping[default_params_holder] = list()

        placements = Placements()

        # add LPG's (1 for each ethernet connected chip
        vertex = LivePacketGather(**default_params)
        app_graph.add_vertex(vertex)
        mac_vertex = LivePacketGatherMachineVertex(**default_params)
        graph.add_vertex(mac_vertex)
        app_graph_mapper.add_vertex_mapping(mac_vertex, Slice(0, 0), vertex)
        placements.add_placement(Placement(x=0, y=0, p=2, vertex=mac_vertex))
        live_packet_gatherers_to_vertex_mapping[
            default_params_holder].append(mac_vertex)

        vertex = LivePacketGather(**default_params)
        app_graph.add_vertex(vertex)
        mac_vertex = LivePacketGatherMachineVertex(**default_params)
        graph.add_vertex(mac_vertex)
        app_graph_mapper.add_vertex_mapping(mac_vertex, Slice(0, 0), vertex)
        placements.add_placement(Placement(x=4, y=8, p=2, vertex=mac_vertex))
        live_packet_gatherers_to_vertex_mapping[
            default_params_holder].append(mac_vertex)

        vertex = LivePacketGather(**default_params)
        mac_vertex = LivePacketGatherMachineVertex(**default_params)
        graph.add_vertex(mac_vertex)
        app_graph_mapper.add_vertex_mapping(mac_vertex, Slice(0, 0), vertex)
        placements.add_placement(Placement(x=8, y=4, p=2, vertex=mac_vertex))
        app_graph.add_vertex(vertex)
        live_packet_gatherers_to_vertex_mapping[
            default_params_holder].append(mac_vertex)

        # tracker of wirings
        verts_expected_0_0 = list()
        verts_expected_4_8 = list()
        verts_expected_8_4 = list()

        positions = list()
        positions.append([0, 0, verts_expected_0_0])
        positions.append([4, 4, verts_expected_0_0])
        positions.append([1, 1, verts_expected_0_0])
        positions.append([2, 2, verts_expected_0_0])
        positions.append([8, 4, verts_expected_8_4])
        positions.append([11, 4, verts_expected_8_4])
        positions.append([4, 11, verts_expected_4_8])
        positions.append([4, 8, verts_expected_4_8])
        positions.append([0, 11, verts_expected_8_4])
        positions.append([11, 11, verts_expected_4_8])
        positions.append([8, 8, verts_expected_4_8])
        positions.append([4, 0, verts_expected_0_0])
        positions.append([7, 7, verts_expected_0_0])

        # add graph verts which reside on areas of the machine to ensure
        #  spread over boards.
        for index in range(0, 13):
            mac_vertex = SimpleMachineVertex(resources=ResourceContainer())
            graph.add_vertex(mac_vertex)
            vertex = TestVertex(1)
            app_graph.add_vertex(vertex)
            app_graph_mapper.add_vertex_mapping(mac_vertex, Slice(0,0), vertex)
            live_packet_gatherers[default_params_holder].append(vertex)
            positions[index][2].append(mac_vertex)
            placements.add_placement(Placement(
                x=positions[index][0], y=positions[index][1], p=5,
                vertex=mac_vertex))

        # run edge inserter that should go boom
        edge_inserter = FrontEndCommonInsertEdgesToLivePacketGatherers()
        edge_inserter(
            live_packet_gatherers=live_packet_gatherers, placements=placements,
            live_packet_recorder_recorded_vertex_type=ApplicationVertex,
            live_packet_gatherers_to_vertex_mapping=
            live_packet_gatherers_to_vertex_mapping,
            machine=machine, machine_graph=graph, application_graph=app_graph,
            graph_mapper=app_graph_mapper)

        verts2_expected_0_0 = list(verts_expected_0_0)
        verts2_expected_4_8 = list(verts_expected_4_8)
        verts2_expected_8_4 = list(verts_expected_8_4)

        # verify edges are in the right place
        # check 0 0 lpg
        edges = graph.get_edges_ending_at_vertex(
            placements.get_vertex_on_processor(0, 0, 2))
        for edge in edges:
            verts_expected_0_0.remove(edge.pre_vertex)
        if len(verts_expected_0_0) != 0:
            raise Exception("wasnt wired correctly")

        # check 4 8 LPG
        edges = graph.get_edges_ending_at_vertex(
            placements.get_vertex_on_processor(4, 8, 2))
        for edge in edges:
            verts_expected_4_8.remove(edge.pre_vertex)
        if len(verts_expected_4_8) != 0:
            raise Exception("wasnt wired correctly")

        # check 8 4 LPG
        edges = graph.get_edges_ending_at_vertex(
            placements.get_vertex_on_processor(8, 4, 2))
        for edge in edges:
            verts_expected_8_4.remove(edge.pre_vertex)
        if len(verts_expected_8_4) != 0:
            raise Exception("wasnt wired correctly")

        # check app graph for 0 0
        lpg_machine = placements.get_vertex_on_processor(0, 0, 2)
        lpg_app = app_graph_mapper.get_application_vertex(lpg_machine)
        for vertex in verts2_expected_0_0:

            app_vertex = app_graph_mapper.get_application_vertex(vertex)
            edges = list(app_graph.get_edges_starting_at_vertex(app_vertex))
            if edges[0].post_vertex != lpg_app:
                raise Exception

if __name__ == "__main__":

    test = TestInsertLPGEdges()
    test.test_local_verts_go_to_local_lpgs()
    test.test_local_verts_when_multiple_lpgs_are_local()
    test.test_local_verts_go_to_local_lpgs_app_graph()

