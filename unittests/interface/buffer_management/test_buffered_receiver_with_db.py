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
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import BufferedReceivingData
from spinn_front_end_common.interface.buffer_management.storage_objects\
    .buffered_receiving_data import DB_FILE_NAME
from spinn_front_end_common.interface.config_setup import unittest_setup


class TestBufferedReceivingDataWithDB(unittest.TestCase):

    def setUp(self):
        unittest_setup()

    def test_use_database(self):
        f = os.path.join(FecDataView.get_run_dir_path(), DB_FILE_NAME)
        self.assertFalse(os.path.isfile(f), "no existing DB at first")

        brd = BufferedReceivingData()
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
