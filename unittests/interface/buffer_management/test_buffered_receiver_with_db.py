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
import tempfile
import os
import shutil
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import BufferedReceivingData
from spinn_front_end_common.interface.buffer_management.storage_objects\
    .buffered_receiving_data import DB_FILE_NAME


class TestBufferedReceivingDataWithDB(unittest.TestCase):

    def test_use_database(self):
        d = tempfile.mkdtemp()
        f = os.path.join(d, DB_FILE_NAME)
        try:
            self.assertFalse(os.path.isfile(f), "no existing DB at first")

            brd = BufferedReceivingData(d)
            self.assertTrue(os.path.isfile(f), "DB now exists")

            # TODO missing
            # data, missing = brd.get_region_data(0, 0, 0, 0)
            # self.assertIsNotNone(missing, "data should be 'missing'")
            # self.assertEqual(data, b"")

            brd.store_data_in_region_buffer(0, 0, 0, 0, b"abc")
            brd.flushing_data_from_region(0, 0, 0, 0, b"def")
            brd.store_end_buffering_state(0, 0, 0, 0, "LOLWUT")
            data, missing = brd.get_region_data(0, 0, 0, 0)

            self.assertIsNone(missing, "data shouldn't be 'missing'")
            self.assertEqual(bytes(data), b"abcdef")

            self.assertTrue(os.path.isfile(f), "DB still exists")
        finally:
            shutil.rmtree(d, True)
