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
from spinn_machine.virtual_machine import virtual_machine
from spinn_front_end_common.utilities.utility_objs import DataWritten
from spinn_front_end_common.interface.ds.ds_write_info import DsWriteInfo
from spinn_front_end_common.interface.ds import DataSpecificationTargets


class TestDsWriteInfo(unittest.TestCase):

    def test_dict(self):
        check = dict()
        machine = virtual_machine(2, 2)
        tempdir = tempfile.mkdtemp()
        dst = DataSpecificationTargets(machine, tempdir)
        print(tempdir)
        asDict = DsWriteInfo(dst.get_database())
        c1 = (0, 0, 0)
        foo = DataWritten(123, 12, 23)
        asDict[c1] = foo
        check[c1] = foo
        self.assertEqual(foo, asDict[c1])

        c2 = (1, 1, 3)
        bar = DataWritten(456, 45, 56)
        asDict[c2] = bar
        check[c2] = bar
        self.assertEqual(bar, asDict[c2])

        self.assertEqual(2, len(asDict))

        for key in asDict:
            self.assertEqual(check[key], asDict[key])

        for key, value in iteritems(asDict):
            self.assertEqual(check[key], value)


if __name__ == "__main__":
    unittest.main()
