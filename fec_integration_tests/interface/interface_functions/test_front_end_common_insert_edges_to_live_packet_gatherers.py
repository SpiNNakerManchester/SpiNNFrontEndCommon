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
from pacman.model.placements import Placements, Placement
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.utilities.utility_objs import (
    LivePacketGatherParameters)
from spinn_front_end_common.utility_models import LivePacketGatherMachineVertex
from pacman_test_objects import SimpleTestVertex
from pacman.model.partitioner_splitters import SplitterFixedLegacy
from spinn_front_end_common.interface.interface_functions import (
    lpg_multicast_routing_generator)
from pacman.model.routing_table_by_partition import (
    MulticastRoutingTableByPartition)

class TestInsertLPGEdges(unittest.TestCase):
    """ tests the interaction of the EDGE INSERTION OF LPGS
    """
    def setUp(self):
        unittest_setup()

    def test_local_verts_go_to_local_lpgs_app_graph(self):
        machine = virtual_machine(width=12, height=12)
        app_graph = ApplicationGraph("Test")

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
        for eth in machine.ethernet_connected_chips:
            m_vert = LivePacketGatherMachineVertex(default_params_holder)
            placements.add_placement(Placement(m_vert, eth.x, eth.y, 2))
            live_packet_gatherers_to_vertex_mapping[
                default_params_holder, eth.x, eth.y] = m_vert

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
            vertex.splitter = SplitterFixedLegacy()
            app_graph.add_vertex(vertex)
            vertex_slice = Slice(0, 0)
            resources_required = vertex.get_resources_used_by_atoms(
                vertex_slice)
            mac_vertex = vertex.create_machine_vertex(
                vertex_slice, resources_required)
            vertex.remember_machine_vertex(mac_vertex)
            partition_ids = ["EVENTS"]
            live_packet_gatherers[default_params_holder].append(
                (vertex, partition_ids))
            verts_expected[eth_x, eth_y].append(mac_vertex)
            app_verts_expected.append(vertex)
            placements.add_placement(
                Placement(x=x, y=y, p=5, vertex=mac_vertex))

        # run edge inserter that should go boom
        routing_tables = MulticastRoutingTableByPartition()
        lpg_multicast_routing_generator(
            live_packet_gatherers, placements,
            live_packet_gatherers_to_vertex_mapping, machine, routing_tables)

        # verify route goes from each source to each target
        for chip in machine.ethernet_connected_chips:
            for m_vert in verts_expected[chip.x, chip.y]:
                entry = routing_tables.get_entry_on_coords_for_edge(
                    m_vert, "EVENTS", chip.x, chip.y)
                assert(entry is not None)


if __name__ == "__main__":
    unittest.main()
