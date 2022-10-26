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
import os
from pacman.model.graphs.machine import SimpleMachineVertex
from pacman.model.placements import Placement, Placements
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import BufferDatabase
from spinn_front_end_common.interface.config_setup import unittest_setup


class TestBufferedDatabase(unittest.TestCase):

    def setUp(self):
        unittest_setup()

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