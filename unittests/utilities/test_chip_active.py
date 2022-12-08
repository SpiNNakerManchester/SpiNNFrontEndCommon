# Copyright (c) 2017-2022 The University of Manchester
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

import os
import unittest
from spinn_utilities.exceptions import InvalidDirectory
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.utilities.report_functions import (
    write_chip_active_report)


class TestChipActive(unittest.TestCase):

    def setUp(cls):
        unittest_setup()

    def test_no_params(self):
        try:
            write_chip_active_report()
            failed = False
        except Exception as ex:
            self.assertIn("no such table", str(ex))
            failed = True
        self.assertTrue(failed)

    def test_db_only(self):
        # make sure there is not run_dir_path so falls back on default
        writer = FecDataWriter.setup()
        try:
            writer.set_run_dir_path("THIS DIRECTORY DOES NOT EXIST")
        except InvalidDirectory:
            pass
        db_path = os.path.join(os.path.dirname(__file__), "buffer.sqlite3")
        write_chip_active_report(buffer_path=db_path)

    def test_all_params(self):
        # make sure there is not run_dir_path so falls back on default
        writer = FecDataWriter.setup()
        try:
            writer.set_run_dir_path("THIS DIRECTORY DOES NOT EXIST")
        except InvalidDirectory:
            pass
        db_path = os.path.join(os.path.dirname(__file__), "buffer.sqlite3")
        report = os.path.join(os.path.dirname(__file__), "my_active.rpt")
        write_chip_active_report(report_path=report, buffer_path=db_path)


if __name__ == '__main__':
    unittest.main()
