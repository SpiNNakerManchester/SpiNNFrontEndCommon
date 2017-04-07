import unittest
from spinn_front_end_common.utilities import helpful_functions


class TestHelpfulFunctions(unittest.TestCase):

    def test_sort_out_downed_cores_chip_links(self):
        down_chips, down_cores, down_links =\
            helpful_functions.sort_out_downed_chips_cores_links(
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
