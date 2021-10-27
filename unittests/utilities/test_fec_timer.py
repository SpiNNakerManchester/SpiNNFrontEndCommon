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
from testfixtures import LogCapture
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.utilities import FecTimer


class MockSimulator(object):

    @property
    def _report_default_directory(self):
        return tempfile.mkdtemp()

    @property
    def n_calls_to_run(self):
        return 1

    @property
    def n_loops(self):
        return 1


class TestFecTimer(unittest.TestCase):

    def setUp(cls):
        unittest_setup()
        FecTimer.setup(MockSimulator())

    def test_simple(self):
        with FecTimer("cat", "test"):
            pass

    def test_error(self):
        with LogCapture() as lc:
            try:
                with FecTimer("cat", "oops"):
                    1/0
            except ZeroDivisionError:
                pass
            found = False
            for record in lc.records:
                if "oops" in str(record.msg):
                    found = True
            assert found


if __name__ == '__main__':
    unittest.main()
