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
