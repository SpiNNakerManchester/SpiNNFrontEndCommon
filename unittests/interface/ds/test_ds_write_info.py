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


class TestDsWriteInfo(unittest.TestCase):

    def setUp(self):
        unittest_setup()
        raise self.skipTest("needs fixing")

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
