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
import os
from pacman.model.graphs.machine import SimpleMachineVertex
from pacman.model.placements import Placement, Placements
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import BufferDatabase
from spinn_front_end_common.interface.config_setup import unittest_setup


class TestBufferedDatabase(unittest.TestCase):

    def setUp(self):
        unittest_setup(board_type=1)

    def test_use_database(self):
        f = BufferDatabase.default_database_file()
        self.assertFalse(os.path.isfile(f), "no existing DB at first")

        with BufferDatabase() as brd:
            self.assertTrue(os.path.isfile(f), "DB now exists")

            # TODO missing
            # data, missing = brd.get_region_data(0, 0, 0, 0)
            # self.assertTrue(missing, "data should be 'missing'")
            # self.assertEqual(data, b"")

            brd.store_data_in_region_buffer(0, 0, 0, 0, False, b"abc")
            brd.store_data_in_region_buffer(0, 0, 0, 0, False, b"def")
            data, missing = brd.get_region_data(0, 0, 0, 0)

            self.assertFalse(missing, "data shouldn't be 'missing'")
            self.assertEqual(bytes(data), b"abcdef")

            self.assertTrue(os.path.isfile(f), "DB still exists")

    def test_placements(self):
        writer = FecDataWriter.mock()
        info = Placements([])
        p1 = Placement(SimpleMachineVertex(None, label="V1"), 1, 2, 3)
        info.add_placement(p1)
        v2 = SimpleMachineVertex(None, label="V2")
        p2 = Placement(v2, 1, 2, 5)
        info.add_placement(p2)
        info.add_placement(Placement(SimpleMachineVertex(None), 2, 2, 3))
        writer.set_placements(info)
        with BufferDatabase() as db:
            db.store_data_in_region_buffer(1, 2, 3, 0, False, b"abc")
            db.store_vertex_labels()
            label = db.get_core_name(1, 2, 3)
            self.assertEqual("V1", label)
            label = db.get_core_name(1, 2, 5)
            self.assertEqual("V2", label)
            label = db.get_core_name(4, 3, 0)
            self.assertEqual("SCAMP(OS)_4:3", label)
