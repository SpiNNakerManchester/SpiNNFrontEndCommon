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
from spinn_machine import virtual_machine
from spinnman.messages.eieio import EIEIOType
from pacman.model.graphs.application import ApplicationGraph, ApplicationVertex
from pacman.model.graphs.machine import MachineGraph
from pacman_test_objects import SimpleTestVertex
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.interface_functions import (
    InsertLivePacketGatherersToGraphs)
from spinn_front_end_common.utilities.utility_objs import (
    LivePacketGatherParameters)


class TestInsertLPGs(unittest.TestCase):
    """ tests the LPG insert functions

    """
    def setUp(self):
        unittest_setup()

    def test_that_3_lpgs_are_generated_on_3_board(self):
        machine = virtual_machine(width=12, height=12)
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

        # run edge inserter that should go boom
        edge_inserter = InsertLivePacketGatherersToGraphs()
        lpg_verts_mapping = edge_inserter(
            live_packet_gatherer_parameters=live_packet_gatherers,
            machine=machine, machine_graph=graph,
            application_graph=ApplicationGraph("empty"))

        self.assertEqual(len(lpg_verts_mapping[default_params_holder][1]), 3)
        locs = [(0, 0), (4, 8), (8, 4)]
        for vertex in lpg_verts_mapping[default_params_holder][1].values():
            x = list(vertex.constraints)[0].x
            y = list(vertex.constraints)[0].y
            key = (x, y)
            locs.remove(key)

        self.assertEqual(len(locs), 0)

        verts = lpg_verts_mapping[default_params_holder][1].values()
        for vertex in graph.vertices:
            self.assertIn(vertex, verts)

    def test_that_3_lpgs_are_generated_on_3_board_app_graph(self):
        machine = virtual_machine(width=12, height=12)
        app_graph = ApplicationGraph("Test")
        app_graph.add_vertex(
            SimpleTestVertex(10, "New AbstractConstrainedVertex 1", 256))
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

        # run edge inserter that should go boom
        edge_inserter = InsertLivePacketGatherersToGraphs()
        lpg_verts_mapping = edge_inserter(
            live_packet_gatherer_parameters=live_packet_gatherers,
            machine=machine, machine_graph=graph, application_graph=app_graph)

        self.assertEqual(len(lpg_verts_mapping[default_params_holder][1]), 3)
        locs = list()
        locs.append((0, 0))
        locs.append((4, 8))
        locs.append((8, 4))
        for vertex in lpg_verts_mapping[default_params_holder][1].values():
            x = list(vertex.constraints)[0].x
            y = list(vertex.constraints)[0].y
            key = (x, y)
            locs.remove(key)

        self.assertEqual(len(locs), 0)

        verts = lpg_verts_mapping[default_params_holder][1].values()
        for vertex in graph.vertices:
            self.assertIn(vertex, verts)

        app_verts = set()
        for vertex in lpg_verts_mapping[default_params_holder][1].values():
            app_vertex = vertex.app_vertex
            self.assertIsNotNone(app_vertex)
            self.assertIsInstance(app_vertex, ApplicationVertex)
            app_verts.add(app_vertex)
        # Should only be a single app vertex for one set of params
        self.assertEqual(len(app_verts), 1)


if __name__ == "__main__":
    unittest.main()
