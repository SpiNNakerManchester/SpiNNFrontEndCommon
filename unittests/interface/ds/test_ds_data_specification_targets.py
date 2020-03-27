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

import tempfile
import unittest
from six import iteritems
from spinn_front_end_common.interface.ds import (
    DataSpecificationTargets, DataRowReader)
from spinn_machine.virtual_machine import virtual_machine


class TestDataSpecificationTargets(unittest.TestCase):
    machine = virtual_machine(2, 2)

    def test_dict(self):
        check = dict()
        testdir = tempfile.mkdtemp()
        print(testdir)
        asDict = DataSpecificationTargets(self.machine, testdir)
        c1 = (0, 0, 0)
        foo = bytearray(b"foo")
        with asDict.create_data_spec(0, 0, 0) as writer:
            writer.write(foo)
        check[c1] = DataRowReader(foo)
        self.assertEqual(check[c1], asDict[c1])

        c2 = (0, 1, 2)
        bar = bytearray(b"bar")
        with asDict.create_data_spec(0, 1, 2) as writer:
            writer.write(bar)
        check[c2] = DataRowReader(bar)
        self.assertEqual(check[c2], asDict[c2])

        self.assertEqual(2, len(asDict))

        asDict.set_app_id(12)

        for key in asDict:
            self.assertEqual(check[key], asDict[key])
            (x, y, p) = key
            self.assertEqual(12, asDict.get_app_id(x, y, p))

        for key, value in iteritems(asDict):
            self.assertEqual(check[key], value)


if __name__ == "__main__":
    unittest.main()
