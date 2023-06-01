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
from spinn_machine.virtual_machine import virtual_machine
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.ds import DsSqlliteDatabase


class TestDataSpecificationTargets(unittest.TestCase):

    def setUp(self):
        unittest_setup()
        raise self.skipTest("needs fixing")

    def test_dict(self):
        FecDataWriter.mock().set_machine(virtual_machine(2, 2))
        check = dict()
        db = DsSqlliteDatabase()
        foo = bytearray(b"foo")
        db.write_data_spec(0, 0, 0, foo)
        c1 = (0, 0, 0)
        check[c1] = foo
        self.assertEqual(check[c1], db.get_ds(0, 0, 0))

        c2 = (0, 1, 2)
        bar = bytearray(b"bar")
        db.write_data_spec(0, 1, 2, bar)
        check[c2] = bar
        self.assertEqual(check[c2], db.get_ds(0, 1, 2))

        self.assertEqual(2, db.get_n_ds_cores())

        db.set_app_id(12)

        for key, value in db.items():
            self.assertEqual(check[key], value.getvalue())


if __name__ == "__main__":
    unittest.main()
