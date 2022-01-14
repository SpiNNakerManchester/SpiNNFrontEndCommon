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
from spinn_utilities.data.data_status import Data_Status
# hack do not copy
from spinn_utilities.data.utils_data_writer import _UtilsDataModel
from spinn_utilities.exceptions import (
    DataNotYetAvialable, NotSetupException)
from pacman.model.routing_tables import MulticastRoutingTables
from spinn_front_end_common.interface.buffer_management import BufferManager
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.data.fec_data_writer import FecDataWriter


class TestSimulatorData(unittest.TestCase):

    def setUp(cls):
        unittest_setup()

    def test_setup(self):
        # What happens before setup depends on the previous test
        # Use manual_check to verify this without dependency
        writer = FecDataWriter.setup()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_simulation_time_step_us()
        writer.set_up_timings(1000, 1)
        FecDataView.get_simulation_time_step_us()

    def test_run(self):
        writer = FecDataWriter.setup()
        self.assertEqual(1, FecDataView.get_n_calls_to_run())
        writer.start_run()
        self.assertEqual(1, FecDataView.get_n_calls_to_run())
        self.assertIn("run_1", FecDataView.get_run_dir_path())
        writer.finish_run()
        self.assertEqual(2, FecDataView.get_n_calls_to_run())
        writer.start_run()
        self.assertEqual(2, FecDataView.get_n_calls_to_run())
        # No reset so run director does not change
        self.assertIn("run_1", FecDataView.get_run_dir_path())
        writer.finish_run()
        writer.start_run()
        self.assertEqual(3, FecDataView.get_n_calls_to_run())
        writer.hard_reset()
        self.assertIn("run_3", FecDataView.get_run_dir_path())

    def test_mock(self):
        # check there is a value not what it is
        self.assertIsNotNone(FecDataView.get_app_id())
        self.assertIsNotNone(FecDataView.get_simulation_time_step_us())

    def test_multiple(self):
        view = FecDataView()
        writer = FecDataWriter.setup()
        view2 = FecDataView()
        writer.set_app_id(7)
        self.assertEqual(7, view.get_app_id())
        self.assertEqual(7, view2.get_app_id())
        self.assertEqual(7, FecDataView.get_app_id())
        self.assertEqual(7, writer.get_app_id())

    def test_app_id(self):
        writer = FecDataWriter.setup()
        app_id1 = writer.get_app_id()
        self.assertEqual(app_id1, writer.get_app_id())
        self.assertEqual(app_id1, writer.get_app_id())
        writer.clear_app_id()
        self.assertNotEqual(app_id1, writer.get_app_id())
        writer.hard_reset()
        self.assertEqual(app_id1, writer.get_app_id())

    def test_buffer_manager(self):
        writer = FecDataWriter.setup()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_buffer_manager()
        self.assertFalse(FecDataView.has_buffer_manager())
        bm = BufferManager(
            extra_monitor_cores=None,
            packet_gather_cores_to_ethernet_connection_map=None,
            extra_monitor_to_chip_mapping=None, fixed_routes=None)
        writer.set_buffer_manager(bm)
        self.assertEqual(bm, FecDataView.get_buffer_manager())
        self.assertTrue(FecDataView.has_buffer_manager())
        writer.hard_reset()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_buffer_manager()
        self.assertFalse(FecDataView.has_buffer_manager())
        with self.assertRaises(TypeError):
            writer.set_buffer_manager("bacon")


    def test_run_times(self):
        writer = FecDataWriter.setup()
        self.assertEqual(0, FecDataView.get_first_machine_time_step())
        self.assertEqual(0, FecDataView.get_current_run_timesteps())
        writer.increment_current_run_timesteps(105)
        self.assertEqual(0, FecDataView.get_first_machine_time_step())
        self.assertEqual(105, FecDataView.get_current_run_timesteps())
        writer.increment_current_run_timesteps(95)
        self.assertEqual(105, FecDataView.get_first_machine_time_step())
        self.assertEqual(200, FecDataView.get_current_run_timesteps())
        writer.increment_current_run_timesteps(0)
        self.assertEqual(200, FecDataView.get_first_machine_time_step())
        self.assertEqual(200, FecDataView.get_current_run_timesteps())
        writer.hard_reset()
        self.assertEqual(0, FecDataView.get_first_machine_time_step())
        self.assertEqual(0,  FecDataView.get_current_run_timesteps())
        with self.assertRaises(TypeError):
            writer.increment_current_run_timesteps(45.0)
        with self.assertRaises(ConfigurationException):
            writer.increment_current_run_timesteps(-1)
        writer.increment_current_run_timesteps(95)
        with self.assertRaises(NotImplementedError):
            writer.increment_current_run_timesteps(None)

    def test_run_forever(self):
        writer = FecDataWriter.setup()
        writer.increment_current_run_timesteps(None)
        self.assertEqual(0, FecDataView.get_first_machine_time_step())
        self.assertIsNone(FecDataView.get_current_run_timesteps())
        with self.assertRaises(NotImplementedError):
            writer.increment_current_run_timesteps(None)
        with self.assertRaises(NotImplementedError):
            writer.increment_current_run_timesteps(100)

    def test_current_run_times_ms(self):
        writer = FecDataWriter.setup()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_current_run_time_ms()
        writer.set_up_timings(500, 4)
        self.assertEqual(0, FecDataView.get_current_run_time_ms())
        writer.increment_current_run_timesteps(88)
        self.assertEqual(44, FecDataView.get_current_run_time_ms())

    def test_max_run_time_steps(self):
        writer = FecDataWriter.setup()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_max_run_time_steps()
        self.assertFalse(FecDataView.has_max_run_time_steps())
        writer.set_max_run_time_steps(13455)
        self.assertEqual(13455, writer.get_max_run_time_steps())
        self.assertEqual(13455, FecDataView.get_max_run_time_steps())
        self.assertTrue(FecDataView.has_max_run_time_steps)

        with self.assertRaises(TypeError):
            writer.set_max_run_time_steps(45.0)
        with self.assertRaises(ConfigurationException):
            writer.set_max_run_time_steps(-1)
        with self.assertRaises(ConfigurationException):
            writer.set_max_run_time_steps(0)

    def test_simulation_timestep(self):
        view = FecDataView()
        writer = FecDataWriter.setup()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_simulation_time_step_us()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_simulation_time_step_per_ms()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_simulation_time_step_per_s()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_simulation_time_step_ms()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_simulation_time_step_s()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_time_scale_factor()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_hardware_time_step_ms()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_hardware_time_step_us()
        self.assertFalse(FecDataView.has_time_step())

        writer.set_up_timings(500, 4)
        self.assertEqual(500, FecDataView.get_simulation_time_step_us())
        self.assertEqual(0.5, FecDataView.get_simulation_time_step_ms())
        self.assertEqual(2, FecDataView.get_simulation_time_step_per_ms())
        self.assertEqual(0.0005, FecDataView.get_simulation_time_step_s())
        self.assertEqual(2000, FecDataView.get_simulation_time_step_per_s())
        self.assertEqual(4, FecDataView.get_time_scale_factor())
        self.assertEqual(2000, FecDataView.get_hardware_time_step_us())
        self.assertEqual(2, FecDataView.get_hardware_time_step_ms())
        self.assertTrue(FecDataView.has_time_step())

        set_config("Machine", "simulation_time_step", 300)
        writer.set_up_timings(None, 1)
        self.assertEqual(300, FecDataView.get_simulation_time_step_us())

        with self.assertRaises(ConfigurationException):
            writer.set_up_timings(-12, 1)

        with self.assertRaises(TypeError):
            writer.set_up_timings("bacon", 1)
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_simulation_time_step_us()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_simulation_time_step_per_ms()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_simulation_time_step_per_s()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_simulation_time_step_ms()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_simulation_time_step_s()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_time_scale_factor()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_hardware_time_step_ms()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_hardware_time_step_us()
        self.assertFalse(view.has_time_step())

    def test_directories_normal(self):
        FecDataWriter.setup()
        report_dir = FecDataView.get_report_dir_path()
        self.assertTrue(os.path.exists(report_dir))

        timestramp_dir = FecDataView.get_timestamp_dir_path()
        self.assertTrue(os.path.exists(report_dir))
        self.assertIn(report_dir, timestramp_dir)

        run_dir = FecDataView.get_run_dir_path()
        self.assertTrue(os.path.exists(run_dir))
        self.assertIn(timestramp_dir, run_dir)

        dir = FecDataView.get_json_dir_path()
        self.assertTrue(os.path.exists(dir))
        self.assertIn(run_dir, dir)

        dir = FecDataView.get_provenance_dir_path()
        self.assertTrue(os.path.exists(dir))
        self.assertIn(run_dir, dir)

        dir2 = FecDataView.get_app_provenance_dir_path()
        self.assertTrue(os.path.exists(dir))
        self.assertIn(run_dir, dir2)
        self.assertIn(dir, dir2)

        dir2 = FecDataView.get_system_provenance_dir_path()
        self.assertTrue(os.path.exists(dir))
        self.assertIn(run_dir, dir2)
        self.assertIn(dir, dir2)

    def test_directories_reset(self):
        writer = FecDataWriter.setup()
        run_dir = FecDataView.get_run_dir_path()
        self.assertIn("run_1", run_dir)
        writer.start_run()
        run_dir = FecDataView.get_run_dir_path()
        self.assertIn("run_1", run_dir)
        writer.finish_run()
        run_dir = FecDataView.get_run_dir_path()
        self.assertIn("run_1", run_dir)
        writer.start_run()
        run_dir = FecDataView.get_run_dir_path()
        self.assertIn("run_1", run_dir)
        writer.finish_run()
        run_dir = FecDataView.get_run_dir_path()
        self.assertIn("run_1", run_dir)
        writer.hard_reset()
        run_dir = FecDataView.get_run_dir_path()
        self.assertIn("run_3", run_dir)
        writer.start_run()
        run_dir = FecDataView.get_run_dir_path()
        self.assertIn("run_3", run_dir)
        writer.finish_run()
        run_dir = FecDataView.get_run_dir_path()
        self.assertIn("run_3", run_dir)

    def test_directories_mocked(self):
        FecDataWriter.mock()
        self.assertTrue(os.path.exists(FecDataView.get_run_dir_path()))
        self.assertTrue(os.path.exists(FecDataView.get_timestamp_dir_path()))
        self.assertTrue(os.path.exists(FecDataView.get_run_dir_path()))
        self.assertTrue(os.path.exists(FecDataView.get_json_dir_path()))
        self.assertTrue(os.path.exists(FecDataView.get_provenance_dir_path()))
        self.assertTrue(os.path.exists(
            FecDataView.get_app_provenance_dir_path()))
        self.assertTrue(os.path.exists(
            FecDataView.get_system_provenance_dir_path()))

    def test_directories_not_setup(self):
        writer = FecDataWriter.mock()
        # Hacks as normally not done
        writer._FecDataWriter__fec_data._clear()
        # VERY UGLY HACK DO NOT COPY!!!!!!!!!!!!
        _UtilsDataModel()._status = Data_Status.NOT_SETUP
        with self.assertRaises(NotSetupException):
            FecDataView.get_report_dir_path()
        with self.assertRaises(NotSetupException):
            FecDataView.get_timestamp_dir_path()
        with self.assertRaises(NotSetupException):
            FecDataView.get_run_dir_path()
        with self.assertRaises(NotSetupException):
            FecDataView.get_json_dir_path()
        with self.assertRaises(NotSetupException):
            FecDataView.get_provenance_dir_path()
        with self.assertRaises(NotSetupException):
            FecDataView.get_app_provenance_dir_path()
        with self.assertRaises(NotSetupException):
            FecDataView.get_system_provenance_dir_path()

    def test_get_n_calls_to_run(self):
        writer = FecDataWriter.setup()
        self.assertTrue(FecDataWriter.has_n_calls_to_run())
        self.assertEqual(1, FecDataView.get_n_calls_to_run())
        writer.start_run()
        self.assertEqual(1, FecDataView.get_n_calls_to_run())
        writer.finish_run()
        self.assertEqual(2, FecDataView.get_n_calls_to_run())
        writer.start_run()
        self.assertEqual(2, FecDataView.get_n_calls_to_run())

    def test_system_multicast_routing_data(self):
        writer = FecDataWriter.setup()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_data_in_multicast_key_to_chip_map()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_data_in_multicast_routing_tables()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_system_multicast_router_timeout_keys()
        data_in_multicast_key_to_chip_map = dict()
        data_in_multicast_routing_tables = MulticastRoutingTables()
        system_multicast_router_timeout_keys = dict()
        data = (data_in_multicast_routing_tables,
                data_in_multicast_key_to_chip_map,
                system_multicast_router_timeout_keys)
        writer.set_system_multicast_routing_data(data)
        self.assertEqual(data_in_multicast_key_to_chip_map,
                         FecDataView.get_data_in_multicast_key_to_chip_map())
        self.assertEqual(data_in_multicast_routing_tables,
                         FecDataWriter.get_data_in_multicast_routing_tables())
        self.assertEqual(
            system_multicast_router_timeout_keys,
            FecDataWriter.get_system_multicast_router_timeout_keys())

        writer.hard_reset()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_data_in_multicast_key_to_chip_map()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_data_in_multicast_routing_tables()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_system_multicast_router_timeout_keys()
