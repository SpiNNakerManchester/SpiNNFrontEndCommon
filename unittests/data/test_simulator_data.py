# Copyright (c) 2021 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import unittest
from spinn_utilities.config_holder import set_config
# hack do not copy
from spinn_utilities.data.data_status import DataStatus
# hack do not copy
from spinn_utilities.data.utils_data_writer import _UtilsDataModel
from spinn_utilities.exceptions import (
    DataNotYetAvialable, NotSetupException)
from spinnman.messages.scp.enums.signal import Signal
from spinn_utilities.socket_address import SocketAddress
from spinnman.model import ExecutableTargets
from pacman.model.placements import Placements
from pacman.model.routing_tables import MulticastRoutingTables
from pacman_test_objects import SimpleTestVertex
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.buffer_management import BufferManager
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.notification_protocol import (
    NotificationProtocol)
from spinn_front_end_common.utilities.utility_objs import (
    LivePacketGatherParameters)
from spinn_front_end_common.utility_models import (
    DataSpeedUpPacketGatherMachineVertex,
    ExtraMonitorSupportMachineVertex)


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

    def test_mock(self):
        # check there is a value not what it is
        self.assertIsNotNone(FecDataView.get_app_id())
        self.assertIsNotNone(FecDataView.get_simulation_time_step_us())

    def test_app_id(self):
        writer = FecDataWriter.setup()
        app_id1 = writer.get_app_id()
        self.assertEqual(app_id1, writer.get_app_id())
        self.assertEqual(app_id1, writer.get_app_id())
        writer.start_run()
        writer.finish_run()
        writer.hard_reset()
        self.assertEqual(app_id1, writer.get_app_id())

    def test_buffer_manager(self):
        writer = FecDataWriter.setup()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_buffer_manager()
        self.assertFalse(FecDataView.has_buffer_manager())
        writer.set_placements(Placements())
        bm = BufferManager()
        writer.set_buffer_manager(bm)
        self.assertEqual(bm, FecDataView.get_buffer_manager())
        self.assertTrue(FecDataView.has_buffer_manager())
        writer.start_run()
        writer.finish_run()
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
        writer.start_run()
        writer.finish_run()
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
        writer = FecDataWriter.setup()
        report_dir = writer.get_report_dir_path()
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
        self.assertEqual(0, writer.get_reset_number())
        self.assertEqual("", writer.get_reset_str())
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
        self.assertEqual(0, writer.get_reset_number())
        writer.hard_reset()
        self.assertEqual(1, writer.get_reset_number())
        self.assertEqual("1", writer.get_reset_str())
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
        _UtilsDataModel()._data_status = DataStatus.NOT_SETUP
        with self.assertRaises(NotSetupException):
            writer.get_report_dir_path()
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

    def test_run_number(self):
        writer = FecDataWriter.setup()
        self.assertEqual(1, FecDataView.get_run_number())
        self.assertIn("run_1", FecDataView.get_run_dir_path())
        writer.start_run()
        self.assertEqual(1, FecDataView.get_run_number())
        self.assertIn("run_1", FecDataView.get_run_dir_path())
        writer.finish_run()
        self.assertEqual(2, FecDataView.get_run_number())
        # run_dir_path only changed on hard reset
        self.assertIn("run_1", FecDataView.get_run_dir_path())
        writer.start_run()
        self.assertEqual(2, FecDataView.get_run_number())
        # run_dir_path only changed on hard reset
        self.assertIn("run_1", FecDataView.get_run_dir_path())
        writer.finish_run()
        self.assertEqual(3, FecDataView.get_run_number())
        # run_dir_path only changed on hard reset
        self.assertIn("run_1", FecDataView.get_run_dir_path())
        self.assertEqual(0, writer.get_reset_number())
        writer.soft_reset()
        self.assertEqual(1, writer.get_reset_number())
        self.assertEqual(3, FecDataView.get_run_number())
        # run_dir_path only changed on hard reset
        self.assertIn("run_1", FecDataView.get_run_dir_path())
        writer.hard_reset()
        self.assertEqual(1, writer.get_reset_number())
        self.assertEqual(3, FecDataView.get_run_number())
        # run_dir_path changed by hard reset
        self.assertIn("run_3", FecDataView.get_run_dir_path())
        writer.start_run()
        self.assertEqual(3, FecDataView.get_run_number())
        self.assertIn("run_3", FecDataView.get_run_dir_path())
        writer.finish_run()
        self.assertEqual(4, FecDataView.get_run_number())
        # run_dir_path only changed on hard reset
        self.assertIn("run_3", FecDataView.get_run_dir_path())

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

        writer.start_run()
        writer.finish_run()
        writer.hard_reset()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_data_in_multicast_key_to_chip_map()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_data_in_multicast_routing_tables()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_system_multicast_router_timeout_keys()

    def test_required(self):
        writer = FecDataWriter.setup()
        with self.assertRaises(DataNotYetAvialable):
            self.assertIsNone(FecDataView.get_n_boards_required())
        self.assertFalse(FecDataView.has_n_boards_required())
        with self.assertRaises(DataNotYetAvialable):
            self.assertIsNone(FecDataView.get_n_chips_needed())
        self.assertFalse(FecDataView.has_n_chips_needed())

        # required higher than in graph
        writer.set_n_required(None, 20)
        self.assertFalse(FecDataView.has_n_boards_required())
        self.assertEqual(20, FecDataView.get_n_chips_needed())
        writer.set_n_chips_in_graph(15)
        self.assertFalse(FecDataView.has_n_boards_required())
        self.assertEqual(20, FecDataView.get_n_chips_needed())

        # required higher than in graph
        writer.set_n_chips_in_graph(25)
        self.assertFalse(FecDataView.has_n_boards_required())
        self.assertEqual(20, FecDataView.get_n_chips_needed())

        # reset does not remove required
        writer.start_run()
        writer.finish_run()
        writer.hard_reset()
        self.assertFalse(FecDataView.has_n_boards_required())
        self.assertEqual(20, FecDataView.get_n_chips_needed())

        writer = FecDataWriter.setup()
        self.assertFalse(FecDataView.has_n_boards_required())
        self.assertFalse(FecDataView.has_n_chips_needed())

        # in graph only
        writer.set_n_chips_in_graph(25)
        self.assertEqual(25, FecDataView.get_n_chips_needed())

        # reset clears in graph
        writer.start_run()
        writer.finish_run()
        writer.hard_reset()
        self.assertFalse(FecDataView.has_n_chips_needed())

        # N boards
        writer = FecDataWriter.setup()
        writer.set_n_required(5, None)
        self.assertEqual(5, FecDataView.get_n_boards_required())
        self.assertFalse(FecDataView.has_n_chips_needed())

        # boards does not hide in graph
        writer.set_n_chips_in_graph(40)
        self.assertEqual(5, FecDataView.get_n_boards_required())
        self.assertEqual(40, FecDataView.get_n_chips_needed())

        # reset does not clear required
        writer.start_run()
        writer.finish_run()
        writer.hard_reset()
        self.assertEqual(5, FecDataView.get_n_boards_required())
        self.assertFalse(FecDataView.has_n_chips_needed())

        # two Nones fine
        writer = FecDataWriter.setup()
        writer.set_n_required(None, None)
        self.assertFalse(FecDataView.has_n_boards_required())
        self.assertFalse(FecDataView.has_n_chips_needed())

        # Ilegal calls
        with self.assertRaises(ConfigurationException):
            writer.set_n_required(5, 5)
        with self.assertRaises(ConfigurationException):
            writer.set_n_required(None, -5)
        with self.assertRaises(ConfigurationException):
            writer.set_n_required(0, None)
        with self.assertRaises(TypeError):
            writer.set_n_required(None, "five")
        with self.assertRaises(TypeError):
            writer.set_n_required("2.3", None)

    def test_ipaddress(self):
        writer = FecDataWriter.setup()
        self.assertFalse(FecDataView.has_ipaddress())
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_ipaddress()
        writer.set_ipaddress("127.0.0.0")
        self.assertEqual("127.0.0.0", FecDataView.get_ipaddress())
        self.assertTrue(FecDataView.has_ipaddress())
        writer.start_run()
        writer.finish_run()
        writer.hard_reset()
        self.assertFalse(FecDataView.has_ipaddress())
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_ipaddress()
        with self.assertRaises(TypeError):
            writer.set_ipaddress(127)

    def test_fixed_routes(self):
        writer = FecDataWriter.setup()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_fixed_routes()
        data = dict()
        writer.set_fixed_routes(data)
        self.assertEqual(data, FecDataView.get_fixed_routes())
        with self.assertRaises(TypeError):
            writer.set_fixed_routes(writer)

    def test_java_caller(self):
        FecDataWriter.setup()
        self.assertFalse(FecDataView.has_java_caller())
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_java_caller()

    def test_next_none_labelled_edge_number(self):
        a = FecDataView.get_next_none_labelled_edge_number()
        b = FecDataView.get_next_none_labelled_edge_number()
        c = FecDataView.get_next_none_labelled_edge_number()
        self.assertEqual(a + 1, b)
        self.assertEqual(b + 1, c)

    def test_next_sync_signal(self):
        writer = FecDataWriter.setup()
        self.assertEqual(Signal.SYNC0, FecDataView.get_next_sync_signal())
        self.assertEqual(Signal.SYNC1, FecDataView.get_next_sync_signal())
        self.assertEqual(Signal.SYNC0, FecDataView.get_next_sync_signal())
        self.assertEqual(Signal.SYNC1, FecDataView.get_next_sync_signal())
        self.assertEqual(Signal.SYNC0, FecDataView.get_next_sync_signal())
        writer.start_run()
        writer.finish_run()
        writer.hard_reset()
        self.assertEqual(Signal.SYNC0, FecDataView.get_next_sync_signal())
        self.assertEqual(Signal.SYNC1, FecDataView.get_next_sync_signal())
        self.assertEqual(Signal.SYNC0, FecDataView.get_next_sync_signal())
        writer.reset_sync_signal()
        self.assertEqual(Signal.SYNC0, FecDataView.get_next_sync_signal())

    def test_executable_types(self):
        writer = FecDataWriter.setup()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_executable_types()
        data = dict()
        writer.set_executable_types(data)
        self.assertEqual(data, FecDataView.get_executable_types())

    def test_live_packet_recorder_params(self):
        writer = FecDataWriter.setup()
        self.assertFalse(FecDataView.has_live_packet_recorder_params())
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_live_packet_recorder_params()
        lpg1 = LivePacketGatherParameters(1)
        lpg2 = LivePacketGatherParameters(2)
        vertex1 = SimpleTestVertex(1, "1")
        vertex2 = SimpleTestVertex(2, "2")
        vertex3 = SimpleTestVertex(3, "3")
        FecDataView.add_vertex(vertex1)
        FecDataView.add_vertex(vertex2)
        FecDataView.add_vertex(vertex3)
        partition_ids1 = ["a"]
        partition_ids2 = ["a", "b"]
        partition_ids3 = ["c"]
        writer.add_live_packet_gatherer_parameters(
            lpg1, vertex1, partition_ids1)
        self.assertTrue(FecDataView.has_live_packet_recorder_params())
        FecDataView.add_live_packet_gatherer_parameters(
            lpg2, vertex2, partition_ids2)
        FecDataView.add_live_packet_gatherer_parameters(
            lpg1, vertex3, partition_ids3)
        params = FecDataView.get_live_packet_recorder_params()
        self.assertEqual(2, len(params))
        self.assertIn(lpg1, params)
        self.assertIn(lpg2, params)

    def test_database_file_path(self):
        writer = FecDataWriter.setup()
        self.assertIsNone(FecDataView.get_database_file_path())
        writer.set_database_file_path(os.getcwd())
        self.assertEqual(os.getcwd(), FecDataView.get_database_file_path())
        writer.start_run()
        writer.finish_run()
        writer.hard_reset()
        self.assertIsNone(FecDataView.get_database_file_path())
        writer.set_database_file_path(os.getcwd())
        writer.set_database_file_path(None)
        self.assertIsNone(FecDataView.get_database_file_path())
        with self.assertRaises(TypeError):
            writer.set_database_file_path(1)

    def test_executable_targets(self):
        writer = FecDataWriter.setup()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_executable_targets()
        targets = ExecutableTargets()
        writer.set_executable_targets(targets)
        self.assertEqual(targets, FecDataView.get_executable_targets())
        with self.assertRaises(TypeError):
            writer.set_executable_targets([])

    def test_gatherer_map(self):
        writer = FecDataWriter.mock()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_gatherer_by_xy(0, 0)
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.iterate_gather_items()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_n_gathers()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.iterate_gathers()
        vertex1 = DataSpeedUpPacketGatherMachineVertex(0, 0, None)
        vertex2 = DataSpeedUpPacketGatherMachineVertex(8, 8, None)
        map = dict()
        # Setting empty ok
        writer.set_gatherer_map(map)
        map[(0, 0)] = vertex1
        map[(8, 8)] = vertex2
        writer.set_gatherer_map(map)
        self.assertEqual(vertex1, FecDataView.get_gatherer_by_xy(0, 0))
        for core, vertex in FecDataView.iterate_gather_items():
            if core == (0, 0):
                self.assertEqual(vertex1, vertex)
            elif core == (8, 8):
                self.assertEqual(vertex2, vertex)
            else:
                raise ValueError(f"Unexpected item {core} {vertex}")
        self.assertCountEqual(
            [vertex1, vertex2], FecDataView.iterate_gathers())
        self.assertEqual(2, FecDataView.get_n_gathers())
        with self.assertRaises(TypeError):
            writer.set_gatherer_map([])
        with self.assertRaises(TypeError):
            map = dict()
            map[(1, 2, 3)] = vertex
            writer.set_gatherer_map(map)
        with self.assertRaises(TypeError):
            map = dict()
            map[(1)] = vertex
            writer.set_gatherer_map(map)
        with self.assertRaises(TypeError):
            map = dict()
            map[(0, 0)] = "Bacon"
            writer.set_gatherer_map(map)
        with self.assertRaises(TypeError):
            map = dict()
            map[(0, "bacon")] = vertex
            writer.set_gatherer_map(map)

    def test_monitor_map(self):
        writer = FecDataWriter.mock()
        self.assertFalse(FecDataView.has_monitors())
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_monitor_by_xy(0, 0)
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.iterate_monitor_items()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_n_monitors()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.iterate_monitors()
        vertex1 = ExtraMonitorSupportMachineVertex()
        vertex2 = ExtraMonitorSupportMachineVertex()
        map = dict()
        # Setting empty ok
        writer.set_monitor_map(map)
        map[(0, 0)] = vertex1
        map[(8, 8)] = vertex2
        writer.set_monitor_map(map)
        self.assertTrue(FecDataView.has_monitors())
        self.assertEqual(vertex1, FecDataView.get_monitor_by_xy(0, 0))
        for core, vertex in FecDataView.iterate_monitor_items():
            if core == (0, 0):
                self.assertEqual(vertex1, vertex)
            elif core == (8, 8):
                self.assertEqual(vertex2, vertex)
            else:
                raise ValueError(f"Unexpected item {core} {vertex}")
        self.assertCountEqual([vertex1, vertex2],
                              FecDataView.iterate_monitors())
        self.assertEqual(2, FecDataView.get_n_monitors())
        with self.assertRaises(KeyError):
            FecDataView.get_monitor_by_xy(1, 1)
        with self.assertRaises(TypeError):
            writer.set_monitor_map([])
        with self.assertRaises(TypeError):
            map = dict()
            map[(1, 2, 3)] = vertex
            writer.set_monitor_map(map)
        with self.assertRaises(TypeError):
            map = dict()
            map[(1)] = vertex
            writer.set_monitor_map(map)
        with self.assertRaises(TypeError):
            map = dict()
            map[(0, 0)] = "Bacon"
            writer.set_monitor_map(map)
        with self.assertRaises(TypeError):
            map = dict()
            map[(0, "bacon")] = vertex
            writer.set_monitor_map(map)

    def test_database_socket_addresses(self):
        FecDataWriter.mock()
        self.assertCountEqual(
            [], FecDataView.iterate_database_socket_addresses())
        sa1 = SocketAddress("a", 2, 3)
        sa2 = SocketAddress("b", 2, 3)
        sa3 = SocketAddress("c", 2, 3)
        sa4 = SocketAddress("d", 2, 3)
        FecDataView.add_database_socket_address(sa1)
        self.assertCountEqual(
            [sa1], FecDataView.iterate_database_socket_addresses())
        FecDataView.add_database_socket_addresses([sa2, sa3])
        self.assertCountEqual(
            [sa1, sa2, sa3], FecDataView.iterate_database_socket_addresses())
        FecDataView.add_database_socket_addresses([sa1, sa4, sa3])
        self.assertCountEqual(
            [sa1, sa2, sa3, sa4],
            FecDataView.iterate_database_socket_addresses())
        with self.assertRaises(TypeError):
            FecDataView.add_database_socket_address("bacon")
        with self.assertRaises(TypeError):
            FecDataView.add_database_socket_addresses(12)

    def test_notification_protocol(self):

        class NotificationProtocol2(NotificationProtocol):

            is_closed = False

            def close(self):
                # record that the method was closed
                self.is_closed = True
                # Now raise an exception
                print(1/0)

        writer = FecDataWriter.setup()
        with self.assertRaises(DataNotYetAvialable):
            FecDataView.get_notification_protocol()
        protocol2 = NotificationProtocol2()
        writer.set_notification_protocol(protocol2)
        self.assertFalse(protocol2.is_closed)
        self.assertEqual(protocol2, FecDataView.get_notification_protocol())
        # closes previous notification_protocol
        writer.set_notification_protocol(NotificationProtocol())
        self.assertTrue(protocol2.is_closed)
        with self.assertRaises(TypeError):
            writer.set_notification_protocol([])

    def test_run_step(self):
        self.assertIsNone(FecDataView.get_run_step())
        writer = FecDataWriter.setup()
        self.assertEqual(1, writer.next_run_step())
        self.assertEqual(1, FecDataView.get_run_step())
        self.assertEqual(2, writer.next_run_step())
        self.assertEqual(3, writer.next_run_step())
        self.assertEqual(3, FecDataView.get_run_step())
        self.assertEqual(3, FecDataView.get_run_step())
        writer.clear_run_steps()
        self.assertIsNone(FecDataView.get_run_step())
        self.assertEqual(1, writer.next_run_step())
        self.assertEqual(1, FecDataView.get_run_step())

    def test_ds_references(self):
        refs1 = FecDataView.get_next_ds_references(7)
        self.assertEqual(7, len(refs1))
        self.assertEqual(7, len(set(refs1)))
        refs2 = FecDataView.get_next_ds_references(5)
        self.assertEqual(5, len(refs2))
        set2 = set(refs2)
        self.assertEqual(5, len(set2))
        self.assertEqual(0, len(set2.intersection(refs1)))

        # reference repeat after a hard reset
        # So if called the same way will generate teh same results
        # setup is also a hard reset
        writer = FecDataWriter.setup()
        self.assertListEqual(refs1, FecDataView.get_next_ds_references(7))
        self.assertListEqual(refs2, FecDataView.get_next_ds_references(5))

        writer.start_run()
        writer.finish_run()
        writer.hard_reset()
        self.assertListEqual(refs1, FecDataView.get_next_ds_references(7))
        self.assertListEqual(refs2, FecDataView.get_next_ds_references(5))
