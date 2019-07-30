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
from spinn_front_end_common.utilities.helpful_functions import (
    sort_out_downed_chips_cores_links)


class TestHelpfulFunctions(unittest.TestCase):

    def test_sort_out_downed_cores_chip_links(self):
        down_chips, down_cores, down_links = sort_out_downed_chips_cores_links(
            "1,1:1,2", "1,2,3:2,3,4", "1,1,3:2,1,2")
        self.assertEqual(
            down_chips, {(1, 1), (1, 2)},
            "Down Chips not parsed correctly")
        self.assertEqual(
            down_cores, {(1, 2, 3), (2, 3, 4)},
            "Down Cores not parsed correctly")
        self.assertEqual(
            down_links, {(1, 1, 3), (2, 1, 2)},
            "Down Links not parsed correctly")


if __name__ == '__main__':
    unittest.main()
