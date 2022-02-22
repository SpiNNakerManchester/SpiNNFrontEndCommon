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


class TestDataSpecificationTargets(unittest.TestCase):

    def setUp(self):
        unittest_setup()

    def test_dict(self):
        FecDataWriter.mock().set_machine(virtual_machine(2, 2))
        check = dict()
        db = DsSqlliteDatabase()
        foo = bytearray(b"foo")
        with db.create_data_spec(0, 0, 0) as writer:
            writer.write(foo)
        c1 = (0, 0, 0)
        check[c1] = foo
        self.assertEqual(check[c1], db.get_ds(0, 0, 0))

        c2 = (0, 1, 2)
        bar = bytearray(b"bar")
        with db.create_data_spec(0, 1, 2) as writer:
            writer.write(bar)
        check[c2] = bar
        self.assertEqual(check[c2], db.get_ds(0, 1, 2))

        self.assertEqual(2, db.ds_n_cores())

        db.set_app_id(12)

        for key, value in db.items():
            self.assertEqual(check[key], value.getvalue())


if __name__ == "__main__":
    unittest.main()
