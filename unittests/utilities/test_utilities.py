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

import os.path
import unittest
from spinn_utilities.config_holder import set_config
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.utilities.utility_calls import (
    get_region_base_address_offset, get_data_spec_and_file_writer_filename)


class TestingUtilities(unittest.TestCase):

    def setUp(cls):
        unittest_setup()

    def test_get_region_base_address_offset(self):
        val = get_region_base_address_offset(48, 7)
        self.assertEqual(val, 84)

    def test_get_data_spec_and_file_writer_filename(self):
        set_config("Reports", "write_text_specs", "True")
        a, b = get_data_spec_and_file_writer_filename(
            2, 3, 5, "example.com", "TEMP")
        self.assertEqual(os.path.split(a)[-1],
                         "example.com_dataSpec_2_3_5.dat")
        # Should be a DSG
        self.assertEqual(b.region_sizes,
                         [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])


if __name__ == '__main__':
    unittest.main()
