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

import os
import unittest
from spinn_utilities.config_holder import set_config
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.utilities.exceptions import (
    ConfigurationException, SimulatorDataNotYetAvialable,
    SimulatorNotSetupException)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.data.data_status import Data_Status
from spinn_front_end_common.data.fec_data_writer import FecDataWriter


class TestSimulatorData(unittest.TestCase):

    def setUp(cls):
        unittest_setup()

    def test_setup(self):
        view = FecDataView()
        writer = FecDataWriter()
        # What happens before setup depends on the previous test
        # Use manual_check to verify this without dependency
        writer.setup()
        with self.assertRaises(SimulatorDataNotYetAvialable):
            view.simulation_time_step_us
        writer.set_up_timings(1000, 1)
        view.simulation_time_step_us

    def test_run(self):
        view = FecDataView()
        writer = FecDataWriter()
        writer.setup()
        self.assertEqual(1, view.n_calls_to_run)
        writer.start_run()
        self.assertEqual(1, view.n_calls_to_run)
        self.assertIn("run_1", view.run_dir_path)
        writer.finish_run()
        self.assertEqual(2, view.n_calls_to_run)
        writer.start_run()
        self.assertEqual(2, view.n_calls_to_run)
        # No reset so run director does not change
        self.assertIn("run_1", view.run_dir_path)

    def test_dict(self):
        view = FecDataView()
        writer = FecDataWriter()
        writer.setup()
        self.assertFalse(view.has_app_id())
        self.assertFalse("APPID" in view)
        with self.assertRaises(KeyError):
            view["APPID"]
        with self.assertRaises(SimulatorDataNotYetAvialable):
            view.app_id
        writer.set_app_id(6)
        self.assertTrue(view.has_app_id())
        self.assertEqual(6, view.app_id)
        self.assertEqual(6, view["APPID"])
        self.assertTrue("APPID" in view)

    def test_mock(self):
        view = FecDataView()
        writer = FecDataWriter()
        writer.mock()
        # check there is a value not what it is
        self.assertIsNotNone(view.app_id)
        self.assertIsNotNone(view.simulation_time_step_us)

    def test_multiple(self):
        view = FecDataView()
        writer = FecDataWriter()
        view2 = FecDataView()
        writer2 = FecDataWriter()
        writer2.set_app_id(7)
        self.assertEqual(7, view.app_id)
        self.assertEqual(7, view2.app_id)
        self.assertEqual(7, writer.app_id)
        self.assertEqual(7, writer2.app_id)

    def test_app_id(self):
        writer = FecDataWriter()
        writer.setup()
        with self.assertRaises(SimulatorDataNotYetAvialable):
            writer.app_id
        self.assertEqual(None, writer.get_app_id())
        self.assertFalse(writer.has_app_id())
        writer.set_app_id(17)
        self.assertEqual(17, writer.get_app_id())
        self.assertEqual(17, writer.app_id)
        self.assertTrue(writer.has_app_id)

    def test_simulation_timestep(self):
        view = FecDataView()
        writer = FecDataWriter()
        writer.setup()
        with self.assertRaises(SimulatorDataNotYetAvialable):
            view.simulation_time_step_us
        with self.assertRaises(SimulatorDataNotYetAvialable):
            view.simulation_time_step_per_ms
        with self.assertRaises(SimulatorDataNotYetAvialable):
            view.simulation_time_step_per_s
        with self.assertRaises(SimulatorDataNotYetAvialable):
            view.simulation_time_step_ms
        with self.assertRaises(SimulatorDataNotYetAvialable):
            view.simulation_time_step_s
        with self.assertRaises(SimulatorDataNotYetAvialable):
            view.time_scale_factor
        with self.assertRaises(SimulatorDataNotYetAvialable):
            view.hardware_time_step_ms
        with self.assertRaises(SimulatorDataNotYetAvialable):
            view.hardware_time_step_us
        self.assertEqual(None, view.get_simulation_time_step_us())
        self.assertEqual(None, view.get_simulation_time_step_ms())
        self.assertEqual(None, view.get_simulation_time_step_s())
        self.assertEqual(None, view.get_simulation_time_step_per_ms())
        self.assertEqual(None, view.get_simulation_time_step_per_s())
        self.assertEqual(None, view.get_time_scale_factor())
        self.assertEqual(None, view.get_hardware_time_step_us())
        self.assertEqual(None, view.get_hardware_time_step_ms())
        self.assertFalse(view.has_time_step())

        writer.set_up_timings(500, 4)
        self.assertEqual(500, view.get_simulation_time_step_us())
        self.assertEqual(0.5, view.get_simulation_time_step_ms())
        self.assertEqual(2, view.get_simulation_time_step_per_ms())
        self.assertEqual(0.0005, view.get_simulation_time_step_s())
        self.assertEqual(2000, view.get_simulation_time_step_per_s())
        self.assertEqual(4, view.get_time_scale_factor())
        self.assertEqual(2000, view.get_hardware_time_step_us())
        self.assertEqual(2, view.get_hardware_time_step_ms())
        self.assertEqual(500, view.simulation_time_step_us)
        self.assertEqual(0.5, view.simulation_time_step_ms)
        self.assertEqual(0.0005, view.simulation_time_step_s)
        self.assertEqual(2, view.simulation_time_step_per_ms)
        self.assertEqual(2000, view.simulation_time_step_per_s)
        self.assertEqual(4, view.time_scale_factor)
        self.assertEqual(2, view.hardware_time_step_ms)
        self.assertEqual(2000, view.hardware_time_step_us)
        self.assertTrue(view.has_time_step())

        set_config("Machine", "simulation_time_step", 300)
        writer.set_up_timings(None, 1)
        self.assertEqual(300, view.get_simulation_time_step_us())

        with self.assertRaises(ConfigurationException):
            writer.set_up_timings(-12, 1)

        with self.assertRaises(TypeError):
            writer.set_up_timings("bacon", 1)
        self.assertEqual(None, view.get_simulation_time_step_us())
        self.assertEqual(None, view.get_simulation_time_step_ms())
        self.assertEqual(None, view.get_simulation_time_step_s())
        self.assertEqual(None, view.get_simulation_time_step_per_ms())
        self.assertEqual(None, view.get_simulation_time_step_per_s())
        self.assertEqual(None, view.get_time_scale_factor())
        self.assertEqual(None, view.get_hardware_time_step_ms())
        self.assertEqual(None, view.get_hardware_time_step_us())

    def test_directories_normal(self):
        writer = FecDataWriter()
        writer.setup()
        report_dir = writer.report_dir_path
        self.assertTrue(os.path.exists(report_dir))

        timestramp_dir = writer.timestamp_dir_path
        self.assertTrue(os.path.exists(report_dir))
        self.assertIn(report_dir, timestramp_dir)

        run_dir = writer.run_dir_path
        self.assertTrue(os.path.exists(run_dir))
        self.assertIn(timestramp_dir, run_dir)

        dir = writer.json_dir_path
        self.assertTrue(os.path.exists(dir))
        self.assertIn(run_dir, dir)

        dir = writer.provenance_dir_path
        self.assertTrue(os.path.exists(dir))
        self.assertIn(run_dir, dir)

        dir2 = writer.app_provenance_dir_path
        self.assertTrue(os.path.exists(dir))
        self.assertIn(run_dir, dir2)
        self.assertIn(dir, dir2)

        dir2 = writer.system_provenance_dir_path
        self.assertTrue(os.path.exists(dir))
        self.assertIn(run_dir, dir2)
        self.assertIn(dir, dir2)

    def test_directories_reset(self):
        writer = FecDataWriter()
        writer.setup()
        run_dir = writer.run_dir_path
        self.assertIn("run_1", run_dir)
        writer.start_run()
        run_dir = writer.run_dir_path
        self.assertIn("run_1", run_dir)
        writer.finish_run()
        run_dir = writer.run_dir_path
        self.assertIn("run_1", run_dir)
        writer.start_run()
        run_dir = writer.run_dir_path
        self.assertIn("run_1", run_dir)
        writer.finish_run()
        run_dir = writer.run_dir_path
        self.assertIn("run_1", run_dir)
        writer.hard_reset()
        run_dir = writer.run_dir_path
        self.assertIn("run_3", run_dir)
        writer.start_run()
        run_dir = writer.run_dir_path
        self.assertIn("run_3", run_dir)
        writer.finish_run()
        run_dir = writer.run_dir_path
        self.assertIn("run_3", run_dir)

    def test_directories_mocked(self):
        writer = FecDataWriter()
        writer.mock()
        self.assertTrue(os.path.exists(writer.report_dir_path))
        self.assertTrue(os.path.exists(writer.timestamp_dir_path))
        self.assertTrue(os.path.exists(writer.run_dir_path))
        self.assertTrue(os.path.exists(writer.json_dir_path))
        self.assertTrue(os.path.exists(writer.provenance_dir_path))
        self.assertTrue(os.path.exists(writer.app_provenance_dir_path))
        self.assertTrue(os.path.exists(writer.system_provenance_dir_path))

    def test_directories_not_setup(self):
        writer = FecDataWriter()
        writer._FecDataWriter__fec_data._clear()
        writer._FecDataWriter__fec_data._status = Data_Status.NOT_SETUP
        with self.assertRaises(SimulatorNotSetupException):
            self.assertTrue(os.path.exists(writer.report_dir_path))
        with self.assertRaises(SimulatorNotSetupException):
            self.assertTrue(os.path.exists(writer.timestamp_dir_path))
        with self.assertRaises(SimulatorNotSetupException):
            self.assertTrue(os.path.exists(writer.run_dir_path))
        with self.assertRaises(SimulatorNotSetupException):
            self.assertTrue(os.path.exists(writer.json_dir_path))
        with self.assertRaises(SimulatorNotSetupException):
            self.assertTrue(os.path.exists(writer.provenance_dir_path))
        with self.assertRaises(SimulatorNotSetupException):
            self.assertTrue(os.path.exists(writer.app_provenance_dir_path))
        with self.assertRaises(SimulatorNotSetupException):
            self.assertTrue(os.path.exists(writer.system_provenance_dir_path))

    def test_get_n_calls_to_run(self):
        view = FecDataView()
        writer = FecDataWriter()
        writer.setup()
        self.assertTrue(view.has_n_calls_to_run())
        self.assertEqual(1, view.n_calls_to_run)
        writer.start_run()
        self.assertEqual(1, view.get_n_calls_to_run())
        writer.finish_run()
        self.assertEqual(2, view.get_n_calls_to_run())
        writer.start_run()
        self.assertEqual(2, view.n_calls_to_run)
