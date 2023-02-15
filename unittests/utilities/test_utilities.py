# Copyright (c) 2017 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os.path
import unittest
from spinn_utilities.config_holder import set_config
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.utilities.helpful_functions import (
    get_region_base_address_offset)
from spinn_front_end_common.utilities.utility_calls import (
     get_data_spec_and_file_writer_filename)


class TestingUtilities(unittest.TestCase):

    def setUp(cls):
        unittest_setup()

    def test_get_region_base_address_offset(self):
        val = get_region_base_address_offset(48, 7)
        self.assertEqual(val, 140)

    def test_get_data_spec_and_file_writer_filename(self):
        set_config("Reports", "write_text_specs", "True")
        a, b = get_data_spec_and_file_writer_filename(2, 3, 5, "TEMP")
        self.assertEqual(os.path.split(a)[-1], "dataSpec_2_3_5.dat")
        # Should be a DSG
        self.assertEqual(b.region_sizes,
                         [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])


if __name__ == '__main__':
    unittest.main()
