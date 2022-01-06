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

import unittest
from collections import defaultdict
from spinn_machine import virtual_machine
from spinnman.messages.eieio import EIEIOType
from pacman.model.graphs.application import ApplicationGraph
from pacman.model.graphs.common import Slice
from pacman.model.graphs.machine import MachineGraph, SimpleMachineVertex
from pacman.model.placements import Placements, Placement
from pacman.model.resources import ResourceContainer
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.interface_functions import (
    insert_edges_to_live_packet_gatherers)
from spinn_front_end_common.utilities.utility_objs import (
    LivePacketGatherParameters)
from spinn_front_end_common.utility_models import (
    LivePacketGather, LivePacketGatherMachineVertex)
from pacman_test_objects import SimpleTestVertex
from pacman.model.partitioner_splitters import SplitterSliceLegacy
from pacman.model.graphs.application.application_edge import ApplicationEdge


class TestInsertLPGEdges(unittest.TestCase):
    """ tests the interaction of the EDGE INSERTION OF LPGS
    """
    def setUp(self):
        unittest_setup()

    def test_local_verts_go_to_local_lpgs(self):
        writer = FecDataWriter.mock()
        machine = virtual_machine(width=12, height=12)
        writer.set_machine(machine)
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
            'tag': None,
            'label': "Test"}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        default_params_holder = LivePacketGatherParameters(**default_params)
        live_packet_gatherers[default_params_holder] = list()

        live_packet_gatherers_to_vertex_mapping = dict()
        mac_vtxs = dict()
        live_packet_gatherers_to_vertex_mapping[default_params_holder] = (
            None, mac_vtxs)

        placements = Placements()

        # add LPG's (1 for each Ethernet connected chip)
        for chip in machine.ethernet_connected_chips:
            extended = dict(default_params)
            extended["label"] = "test"
            vertex = LivePacketGatherMachineVertex(
                LivePacketGatherParameters(**extended))
            graph.add_vertex(vertex)
            placements.add_placement(
                Placement(x=chip.x, y=chip.y, p=2, vertex=vertex))
            mac_vtxs[chip.x, chip.y] = vertex

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
            partition_ids = ["EVENTS"]
            live_packet_gatherers[default_params_holder].append(
                (vertex, partition_ids))
            verts_expected[eth_x, eth_y].append(vertex)
            placements.add_placement(Placement(x=x, y=y, p=5, vertex=vertex))

        writer.set_runtime_machine_graph(graph)
        writer._set_runtime_graph(ApplicationGraph("Empty"))
        writer.set_placements(placements)
        # run edge inserter that should go boom
        insert_edges_to_live_packet_gatherers(
            live_packet_gatherer_parameters=live_packet_gatherers,
            live_packet_gatherers_to_vertex_mapping=(
                live_packet_gatherers_to_vertex_mapping))

        # verify edges are in the right place
        for chip in machine.ethernet_connected_chips:
            edges = graph.get_edges_ending_at_vertex(mac_vtxs[chip.x, chip.y])
            for edge in edges:
                self.assertIn(edge.pre_vertex, verts_expected[chip.x, chip.y])

    def test_local_verts_go_to_local_lpgs_app_graph(self):
        writer = FecDataWriter.mock()
        machine = virtual_machine(width=12, height=12)
        writer.set_machine(machine)

        app_graph = ApplicationGraph("Test")
        graph = MachineGraph("Test", app_graph)

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
            'tag': None,
            'label': "Test"}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        default_params_holder = LivePacketGatherParameters(**default_params)
        live_packet_gatherers[default_params_holder] = list()

        live_packet_gatherers_to_vertex_mapping = dict()

        placements = Placements()

        # add LPG's (1 for each Ethernet connected chip
        lpg_app_vertex = LivePacketGather(
            LivePacketGatherParameters(default_params))
        app_graph.add_vertex(lpg_app_vertex)
        vertex_slice = None
        resources_required = lpg_app_vertex.get_resources_used_by_atoms(
            vertex_slice)
        mac_vtxs = dict()
        live_packet_gatherers_to_vertex_mapping[default_params_holder] = (
            lpg_app_vertex, mac_vtxs)
        for chip in machine.ethernet_connected_chips:
            mac_vertex = lpg_app_vertex.create_machine_vertex(
                vertex_slice, resources_required)
            graph.add_vertex(mac_vertex)
            placements.add_placement(
                Placement(x=chip.x, y=chip.y, p=2, vertex=mac_vertex))
            mac_vtxs[chip.x, chip.y] = mac_vertex

        # tracker of wirings
        verts_expected = defaultdict(list)
        app_verts_expected = list()

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
            vertex = SimpleTestVertex(1)
            vertex.splitter = SplitterSliceLegacy()
            app_graph.add_vertex(vertex)
            app_edge = ApplicationEdge(vertex, lpg_app_vertex)
            app_graph.add_edge(app_edge, "EVENTS")
            lpg_app_vertex.add_incoming_edge(app_edge)
            vertex_slice = Slice(0, 0)
            resources_required = vertex.get_resources_used_by_atoms(
                vertex_slice)
            mac_vertex = vertex.create_machine_vertex(
                vertex_slice, resources_required)
            graph.add_vertex(mac_vertex)
            partition_ids = ["EVENTS"]
            live_packet_gatherers[default_params_holder].append(
                (vertex, partition_ids))
            verts_expected[eth_x, eth_y].append(mac_vertex)
            app_verts_expected.append(vertex)
            placements.add_placement(
                Placement(x=x, y=y, p=5, vertex=mac_vertex))

        writer.set_runtime_machine_graph(graph)
        writer._set_runtime_graph(app_graph)
        writer.set_placements(placements)
        # run edge inserter that should go boom
        insert_edges_to_live_packet_gatherers(
            live_packet_gatherer_parameters=live_packet_gatherers,
            live_packet_gatherers_to_vertex_mapping=(
                live_packet_gatherers_to_vertex_mapping))

        # verify edges are in the right place
        for chip in machine.ethernet_connected_chips:
            edges = graph.get_edges_ending_at_vertex(
                live_packet_gatherers_to_vertex_mapping[
                    default_params_holder][1][chip.x, chip.y])
            for edge in edges:
                self.assertIn(edge.pre_vertex, verts_expected[chip.x, chip.y])

        # check app graph
        for edge in app_graph.get_edges_ending_at_vertex(lpg_app_vertex):
            self.assertIn(edge.pre_vertex, app_verts_expected)


if __name__ == "__main__":
    unittest.main()
