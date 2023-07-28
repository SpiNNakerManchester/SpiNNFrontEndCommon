# Copyright (c) 2017 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from spinn_utilities.config_holder import set_config
from spinn_machine import virtual_machine
from spinnman.messages.eieio import EIEIOType
from pacman.model.graphs.machine import MachineVertex
from pacman.model.placements import Placements
from pacman.model.graphs.application import ApplicationVertex
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.interface_functions import (
    split_lpg_vertices)
from spinn_front_end_common.utilities.utility_objs import (
    LivePacketGatherParameters)
from spinn_front_end_common.utility_models import LivePacketGather


class TestVertex(ApplicationVertex):
    def __init__(self, n_atoms):
        self.n_atoms = n_atoms


class TestInsertLPGs(unittest.TestCase):
    """ tests the LPG insert functions

    """
    def setUp(self):
        unittest_setup()
        set_config("Machine", "version", 5)

    def test_that_3_lpgs_are_generated_on_3_board_app_graph(self):
        writer = FecDataWriter.mock()
        writer.set_machine(virtual_machine(width=12, height=12))

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

        default_params_holder = LivePacketGatherParameters(**default_params)
        lpg_vertex = LivePacketGather(default_params_holder)
        writer.add_vertex(lpg_vertex)

        system_placements = Placements()
        split_lpg_vertices(system_placements)

        locs = set()
        locs.add((0, 0))
        locs.add((4, 8))
        locs.add((8, 4))
        for m_vertex in lpg_vertex.machine_vertices:
            placement = system_placements.get_placement_of_vertex(m_vertex)
            locs.remove((placement.x, placement.y))
            self.assertIsNotNone(m_vertex)
            self.assertIsInstance(m_vertex, MachineVertex)

        self.assertEqual(len(locs), 0)


if __name__ == "__main__":
    unittest.main()
