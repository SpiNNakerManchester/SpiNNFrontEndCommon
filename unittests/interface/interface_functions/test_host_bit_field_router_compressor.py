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
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.interface_functions.\
    host_bit_field_router_compressor import _BitFieldData


class TestHostBasedBitFieldRouterCompressorr(unittest.TestCase):

    def setUp(self):
        unittest_setup()

    def test_bit_field_as_bit_array(self):
        data = _BitFieldData(
            1, [1], None, None, None, None, None)
        as_array = data.bit_field_as_bit_array()
        self.assertListEqual(
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            as_array)


if __name__ == "__main__":
    unittest.main()
