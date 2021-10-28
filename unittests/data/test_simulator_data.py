# Copyright (c) 2021 The University of Manchester
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
from spinn_front_end_common.utilities.exceptions import (
    SimulatorDataNotYetAvialable)
from spinn_front_end_common.data import FecDataView, FecDataWriter


class TestSimulatorData(unittest.TestCase):

    def test_setup(self):
        view = FecDataView()
        writer = FecDataWriter()
        # What happens before setup depends on the previous test
        # Use manual_check to verify this without dependency
        writer.setup()
        self.assertIn("run_1", view.report_default_directory)
        self.assertIn("provenance_data", view.provenance_file_path)
        with self.assertRaises(SimulatorDataNotYetAvialable):
            view.machine_time_step
        writer.set_machine_time_step(10)
        view.machine_time_step

    def test_run(self):
        view = FecDataView()
        writer = FecDataWriter()
        writer.setup()
        self.assertEqual(1, view.n_calls_to_run)
        writer.start_run()
        self.assertEqual(1, view.n_calls_to_run)
        writer.finish_run()
        self.assertEqual(2, view.n_calls_to_run)
        writer.start_run()
        self.assertEqual(2, view.n_calls_to_run)
        self.assertIn("run_1", view.report_default_directory)
