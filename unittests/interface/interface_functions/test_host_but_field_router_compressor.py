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
from spinn_front_end_common.interface.interface_functions.\
    host_bit_field_router_compressor import _BitFieldData


class TestHostBasedBitFieldRouterCompressorr(unittest.TestCase):

    def test_bit_field_as_bit_array_32(self):
        data = _BitFieldData(
            1, [0xF0F0F0F0], None, None, None)
        as_array = data.bit_field_as_bit_array()
        self.assertListEqual(
            [0,0,0,0,1,1,1,1,0,0,0,0,1,1,1,1,0,0,0,0,1,1,1,1,0,0,0,0,1,1,1,1],
            as_array)

    def test_bit_field_as_bit_array(self):
        data = _BitFieldData(
            1, [1], None, None, None)
        as_array = data.bit_field_as_bit_array()
        self.assertListEqual(
            [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
            as_array)


if __name__ == "__main__":
    unittest.main()
