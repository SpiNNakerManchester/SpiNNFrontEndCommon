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
from spinn_front_end_common.utilities.helpful_functions import (
    get_region_base_address_offset)


class TestingUtilities(unittest.TestCase):

    def setUp(cls):
        unittest_setup()

    def test_get_region_base_address_offset(self):
        val = get_region_base_address_offset(48, 7)
        self.assertEqual(val, 140)


if __name__ == '__main__':
    unittest.main()
