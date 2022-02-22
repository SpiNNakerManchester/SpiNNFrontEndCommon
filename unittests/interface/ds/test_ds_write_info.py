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
from spinn_machine.virtual_machine import virtual_machine
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.ds import DsSqlliteDatabase


class TestDsWriteInfo(unittest.TestCase):

    def setUp(self):
        unittest_setup()

    def test_dict(self):
        check = dict()
        FecDataWriter.mock().set_machine(virtual_machine(2, 2))
        db = DsSqlliteDatabase()
        c1 = (0, 0, 0)
        db.set_write_info(*c1, 123, 12, 23)
        check[c1] = (123, 12, 23)
        self.assertEqual((123, 12, 23), db.get_write_info(*c1))

        c2 = (1, 1, 3)
        db.set_write_info(*c2, 456, 45, 56)
        check[c2] = (456, 45, 56)
        self.assertEqual((456, 45, 56), db.get_write_info(*c2))

        for key in check:
            self.assertEqual(check[key], db.get_write_info(*key))

        for key, value in db.items():
            self.assertEqual(check[key], value)


if __name__ == "__main__":
    unittest.main()
