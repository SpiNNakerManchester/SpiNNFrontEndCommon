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
from spinn_utilities.exceptions import InvalidDirectory
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.utilities.report_functions.timer_report import\
    write_timer_report
from spinn_front_end_common.data.fec_data_writer import FecDataWriter


class TestTimerReport(unittest.TestCase):

    def setUp(cls):
        unittest_setup()

    def test_no_params(self):
        try:
            write_timer_report()
            failed = False
        except Exception as ex:
            self.assertIn("no such DB", str(ex))
            failed = True
        self.assertTrue(failed)

    def test_db_only(self):
        # make sure there is not run_dir_path so falls back on default
        writer = FecDataWriter.setup()
        try:
            writer.set_run_dir_path("THIS DIRECTORY DOES NOT EXIST")
        except InvalidDirectory:
            pass
        db_path = os.path.join(os.path.dirname(__file__), "timer.sqlite3")
        write_timer_report(database_file=db_path)

    def test_all_param(self):
        db_path = os.path.join(os.path.dirname(__file__), "timer.sqlite3")
        report_path = os.path.join(os.path.dirname(__file__), "my_timer.rpt")
        write_timer_report(report_path=report_path, database_file=db_path,
                           timer_report_ratio=0.5, timer_report_ms=5,
                           timer_report_to_stdout=False)

    def test_to_screen(self):
        db_path = os.path.join(os.path.dirname(__file__), "timer.sqlite3")
        write_timer_report(database_file=db_path,
                           timer_report_to_stdout=True)


if __name__ == '__main__':
    unittest.main()
