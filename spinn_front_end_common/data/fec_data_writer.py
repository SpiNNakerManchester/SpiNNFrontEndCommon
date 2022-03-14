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

import datetime
import logging
import math
import os
import time
from spinn_utilities.config_holder import (
    get_config_int, get_config_str)
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spinnman.data.spinnman_data_writer import SpiNNManDataWriter
from spinnman.messages.scp.enums.signal import Signal
from spinnman.model import ExecutableTargets
from pacman.data.pacman_data_writer import PacmanDataWriter
from pacman.model.routing_tables import MulticastRoutingTables
from spinn_front_end_common.interface.buffer_management import BufferManager
from spinn_front_end_common.interface.ds import DsSqlliteDatabase
from spinn_front_end_common.interface.java_caller import JavaCaller
from spinn_front_end_common.utilities.constants import (
    MICRO_TO_MILLISECOND_CONVERSION, MICRO_TO_SECOND_CONVERSION)
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utility_models import (
    DataSpeedUpPacketGatherMachineVertex, ExtraMonitorSupportMachineVertex)
from .fec_data_view import FecDataView, _FecDataModel


logger = FormatAdapter(logging.getLogger(__name__))
__temp_dir = None

REPORTS_DIRNAME = "reports"


class FecDataWriter(PacmanDataWriter, SpiNNManDataWriter, FecDataView):
    """
    Writer class for the Fec Data

    """
    __fec_data = _FecDataModel()
    __slots__ = []

    @overrides(PacmanDataWriter._mock)
    def _mock(self):
        PacmanDataWriter._mock(self)
        self._spinnman_mock()
        self.__fec_data._clear()
        # run numbers start at 1 and when not running this is the next one
        self.__fec_data._run_number = 1
        self.set_up_timings(1000, 1)

    @overrides(PacmanDataWriter._setup)
    def _setup(self):
        """
        Puts all data back into the state expected at sim.setup time

        """
        PacmanDataWriter._setup(self)
        self._spinnman_setup()
        self.__fec_data._clear()
        # run numbers start at 1 and when not running this is the next one
        self.__fec_data._run_number = 1
        self.__create_reports_directory()
        self.__create_timestamp_directory()
        self.__create_run_dir_path()

    def start_run(self):
        PacmanDataWriter.start_run(self)

    def finish_run(self):
        PacmanDataWriter.finish_run(self)
        self.__fec_data._run_number += 1

    @overrides(PacmanDataWriter._hard_reset)
    def _hard_reset(self):
        PacmanDataWriter._hard_reset(self)
        SpiNNManDataWriter._local_hard_reset(self)
        self.__fec_data._hard_reset()
        self.__create_run_dir_path()

    @overrides(PacmanDataWriter._soft_reset)
    def _soft_reset(self):
        PacmanDataWriter._soft_reset(self)
        SpiNNManDataWriter._local_soft_reset(self)
        self.__fec_data._soft_reset()

    def __create_run_dir_path(self):
        self.set_run_dir_path(self._child_folder(
            self.__fec_data._timestamp_dir_path,
            f"run_{self.__fec_data._run_number}"))

    def __create_reports_directory(self):
        default_report_file_path = get_config_str(
            "Reports", "default_report_file_path")
        # determine common report folder
        if default_report_file_path == "DEFAULT":
            directory = os.getcwd()

            # global reports folder
            self.__fec_data._report_dir_path = self._child_folder(
                directory, REPORTS_DIRNAME)
        else:
            self.__fec_data._report_dir_path = self._child_folder(
                default_report_file_path, REPORTS_DIRNAME)

    @classmethod
    def __create_timestamp_directory(cls):
        while True:
            try:
                now = datetime.datetime.now()
                timestamp = (
                    f"{now.year:04}-{now.month:02}-{now.day:02}-{now.hour:02}"
                    f"-{now.minute:02}-{now.second:02}-{now.microsecond:06}")
                cls.__fec_data._timestamp_dir_path = cls._child_folder(
                    cls.get_report_dir_path(), timestamp, must_create=True)
                return
            except OSError:
                time.sleep(0.5)

    def set_buffer_manager(self, buffer_manager):
        """
        Sets the Buffer manager variable

        :param BufferManager buffer_manager:
        """
        if not isinstance(buffer_manager, BufferManager):
            raise TypeError("buffer_manager must be a BufferManager")
        self.__fec_data._buffer_manager = buffer_manager

    def increment_current_run_timesteps(self, increment):
        """
        Increment the current_run_timesteps and sets first_machine_time_step

        A None increment signals run_forever

        :param increment: The timesteps for this do_run loop
        :rtype increment: int or None
        """
        if increment is None:
            if self.__fec_data._current_run_timesteps != 0:
                raise NotImplementedError(
                    "Run forever after another run")
            self.__fec_data._current_run_timesteps = None
        else:
            if not isinstance(increment, int):
                raise TypeError("increment should be an int (or None")
            if increment < 0:
                raise ConfigurationException(
                    f"increment {increment} must not be negative")
            if self.__fec_data._current_run_timesteps is None:
                raise NotImplementedError(
                    "Run after run forever")
            self.__fec_data._first_machine_time_step = \
                self.__fec_data._current_run_timesteps
            self.__fec_data._current_run_timesteps += increment

    def set_max_run_time_steps(self, max_run_time_steps):
        """
        Sets the max_run_time_steps value

        :param int max_run_time_steps: new value
        """
        if not isinstance(max_run_time_steps, int):
            raise TypeError("max_run_time_steps should be an int")
        if max_run_time_steps <= 0:
            raise ConfigurationException(
                f"max_run_time_steps {max_run_time_steps} must be possitive")
        self.__fec_data._max_run_time_steps = max_run_time_steps

    def set_up_timings(
            self, simulation_time_step_us, time_scale_factor,
            default_time_scale_factor=None):
        """ Set up timings for the simulation

        :param simulation_time_step_us:
            An explicitly specified time step for the simulation in .
            If None, the value is read from the config
        :type simulation_time_step_us: int or None
        :param time_scale_factor:
            An explicitly specified time scale factor for the simulation.
            If None, the value is read from the config
        :type time_scale_factor: float or None
        :param default_time_scale_factor:
            A back up time scale factor for the simulation.
            Only used if time_scale_factor param and cfg are both None
            If None, the value is based on simulation_time_step
        :type default_time_scale_factor: float or None
        """
        try:
            self._set_simulation_time_step(simulation_time_step_us)
            self._set_time_scale_factor(
                time_scale_factor, default_time_scale_factor)
            self._set_hardware_timestep()
        except ConfigurationException:
            self.__fec_data._simulation_time_step_us = None
            self.__fec_data._simulation_time_step_ms = None
            self.__fec_data._simulation_time_step_per_ms = None
            self.__fec_data._simulation_time_step_per_s = None
            self.__fec_data._simulation_time_step_s = None
            self.__fec_data._time_scale_factor = None
            self.__fec_data._hardware_time_step_us = None
            self.__fec_data._hardware_time_step_ms = None
            raise

    def _set_simulation_time_step(self, simulation_time_step_us):
        """

        :param simulation_time_step_us:
            An explicitly specified time step for the simulation.  If None,
            the value is read from the config
        :type simulation_time_step: int or None
        """
        if simulation_time_step_us is None:
            simulation_time_step_us = get_config_int(
                "Machine", "simulation_time_step")

        if not isinstance(simulation_time_step_us, int):
            raise TypeError("simulation_time_step_us should be an int")

        if simulation_time_step_us <= 0:
            raise ConfigurationException(
                f'invalid simulation_time_step {simulation_time_step_us}'
                f': must greater than zero')

        self.__fec_data._simulation_time_step_us = simulation_time_step_us
        self.__fec_data._simulation_time_step_ms = (
                simulation_time_step_us / MICRO_TO_MILLISECOND_CONVERSION)
        self.__fec_data._simulation_time_step_per_ms = (
                MICRO_TO_MILLISECOND_CONVERSION / simulation_time_step_us)
        self.__fec_data._simulation_time_step_per_s = (
                MICRO_TO_SECOND_CONVERSION / simulation_time_step_us)
        self.__fec_data._simulation_time_step_s = (
                simulation_time_step_us / MICRO_TO_SECOND_CONVERSION)

    def _set_time_scale_factor(
            self, time_scale_factor, default_time_scale_factor):
        """ Set up time_scale_factor

        If time_scale_factor is provide that is used

        Then if cfg is not None that is used

        Then if default is provided that is used

        Lastly it is set based on the simulation_time_step

        :param time_scale_factor:
            An explicitly specified time scale factor for the simulation.
            If None, the value is read from the config
        :type time_scale_factor: float or None
        """
        if time_scale_factor is None:
            # Note while this reads from the cfg the cfg default is None
            time_scale_factor = get_config_int(
                "Machine", "time_scale_factor")

        if time_scale_factor is None:
            if default_time_scale_factor is not None:
                time_scale_factor = default_time_scale_factor

        if time_scale_factor is None:
            time_scale_factor = max(
                1.0, math.ceil(self.get_simulation_time_step_per_ms()))
            if time_scale_factor > 1.0:
                logger.warning(
                    f"A timestep was entered that has forced spinnaker to "
                    f"automatically slow the simulation down from real time "
                    f"by a factor of {time_scale_factor}.")

        if not isinstance(time_scale_factor, (int, float)):
            raise TypeError("app_id should be an int (or float)")

        if time_scale_factor <= 0:
            raise ConfigurationException(
                f'invalid time_scale_factor {time_scale_factor}'
                f': must greater than zero')

        self.__fec_data._time_scale_factor = time_scale_factor

    def _set_hardware_timestep(self):
        raw = (self.get_simulation_time_step_us() *
               self.get_time_scale_factor())
        rounded = round(raw)
        if abs(rounded - raw) > 0.0001:
            raise ConfigurationException(
                f"The multiplication of simulation time step in microseconds: "
                f"{self.get_simulation_time_step_us()} and times scale factor"
                f": {self.get_time_scale_factor()} produced a non integer "
                f"hardware time step of {raw}")

        logger.info(f"Setting hardware timestep as {rounded} microseconds "
                    f"based on simulation time step of "
                    f"{self.get_simulation_time_step_us()} and "
                    f"timescale factor of {self.get_time_scale_factor()}")
        self.__fec_data._hardware_time_step_us = rounded
        self.__fec_data._hardware_time_step_ms = (
                rounded / MICRO_TO_MILLISECOND_CONVERSION)

    def set_system_multicast_routing_data(self, data):
        """
        Sets the system_multicast_routing_data

        These are data_in_multicast_routing_tables,
                 data_in_multicast_key_to_chip_map,
                 system_multicast_router_timeout_keys

        :param tuple(dict, MulticastRoutingTables, dict) data: new value
        """
        (data_in_multicast_routing_tables,
         data_in_multicast_key_to_chip_map,
         system_multicast_router_timeout_keys) = data
        if not isinstance(data_in_multicast_routing_tables,
                          MulticastRoutingTables):
            raise TypeError("First element must be a MulticastRoutingTables")
        if not isinstance(data_in_multicast_key_to_chip_map, dict):
            raise TypeError("Second element must be dict")
        if not isinstance(system_multicast_router_timeout_keys, dict):
            raise TypeError("Third element must be a dict")
        self.__fec_data._data_in_multicast_key_to_chip_map = \
            data_in_multicast_key_to_chip_map
        self.__fec_data._data_in_multicast_routing_tables = \
            data_in_multicast_routing_tables
        self.__fec_data._system_multicast_router_timeout_keys = \
            system_multicast_router_timeout_keys

    def set_n_required(self, n_boards_required, n_chips_required):
        """
        Sets (if not None) the number of boards/chips requested by the user

        :param n_boards_required: None or the number of boards requested by
            the user
        :type n_boards_required: int or None
        :param n_chips_required: None or the number of chips requested by
            the user
        :type n_chips_required: int or None
        """
        if n_boards_required is None:
            if n_chips_required is None:
                return
            elif not isinstance(n_chips_required, int):
                raise TypeError("n_chips_required must be an int (or None)")
            if n_chips_required <= 0:
                raise ConfigurationException(
                    f"n_chips_required must be positive and not "
                    f"{n_chips_required}")
        else:
            if n_chips_required is not None:
                raise ConfigurationException(
                    f"Illegal call with both both param provided as "
                    f"{n_boards_required}, {n_chips_required}")
            if not isinstance(n_boards_required, int):
                raise TypeError("n_boards_required must be an int (or None)")
            if n_boards_required <= 0:
                raise ConfigurationException(
                    f"n_boards_required must be positive and not "
                    f"{n_boards_required}")
        if self.__fec_data._n_boards_required is not None or \
                self.__fec_data._n_chips_required is not None:
            raise ConfigurationException(
                "Illegal second call to set_n_required")
        self.__fec_data._n_boards_required = n_boards_required
        self.__fec_data._n_chips_required = n_chips_required

    def set_n_chips_in_graph(self, n_chips_in_graph):
        if not isinstance(n_chips_in_graph, int):
            raise TypeError("n_chips_in_graph must be an int (or None)")
        if n_chips_in_graph <= 0:
            raise ConfigurationException(
                f"n_chips_in_graph must be positive and not "
                f"{n_chips_in_graph}")
        self.__fec_data._n_chips_in_graph = n_chips_in_graph

    def set_ipaddress(self, ipaddress):
        """

        :param str ipaddress:
        """
        if not isinstance(ipaddress, str):
            raise TypeError("ipaddress must be a str")
        self.__fec_data._ipaddress = ipaddress

    def set_fixed_routes(self, fixed_routes):
        """

        :type fixed_routes:
            dict(tuple(int,int), ~spinn_machine.FixedRouteEntry)
        """
        if not isinstance(fixed_routes, dict):
            raise TypeError("fixed_routes must be a dict")
        self.__fec_data._fixed_routes = fixed_routes

    def set_java_caller(self, java_caller):
        """

        :param  JavaCaller java_caller:
        """
        if not isinstance(java_caller, JavaCaller):
            raise TypeError("java_calle must be a JavaCaller")
        self.__fec_data._java_caller = java_caller

    def reset_sync_signal(self):
        self.__fec_data._next_sync_signal = Signal.SYNC0

    def set_executable_types(self, executable_types):
        """

        :type executable_types:  dict(
            ~spinn_front_end_common.utilities.utility_objs.ExecutableType,
            ~spinn_machine.CoreSubsets or None)
        """
        if not isinstance(executable_types, dict):
            raise TypeError("executable_types must be a Dict")
        self.__fec_data._executable_types = executable_types

    def add_live_packet_gatherer_parameters(
            self, live_packet_gatherer_params, vertex_to_record_from,
            partition_ids):
        """
        Helper method to convert the call back into a class method

        Use the same method on view is preferred
        """
        FecDataView.add_live_packet_gatherer_parameters(
            live_packet_gatherer_params, vertex_to_record_from,
            partition_ids)

    def set_live_packet_gatherer_parameters(self, params):
        """
        testing method will not work outisde of mock
        """
        if not self._is_mocked():
            raise NotImplementedError("This call is only for testing")
        self.__fec_data._live_packet_recorder_params = params

    def set_database_file_path(self, database_file_path):
        """
        Sets the database_file_path variable. Possibly to None

        :type database_file_path: str or None
        """
        if not isinstance(database_file_path, (str, type(None))):
            raise TypeError("database_file_path must be a str or None")
        self.__fec_data._database_file_path = database_file_path

    def set_executable_targets(self, executable_targets):
        """
        Sets the executable_targets

        :type executable_targets: ExecutableTargets
        """
        if not isinstance(executable_targets, ExecutableTargets):
            raise TypeError("executable_targets must be a str or None")
        self.__fec_data._executable_targets = executable_targets

    def set_dsg_targets(self, dsg_targets):
        """
        Sets the data Spec targets database

        :type dsg_targets: ExecutableTargets
        """
        if not isinstance(dsg_targets, DsSqlliteDatabase):
            raise TypeError("dsg_targets must be a DsSqlliteDatabase")
        self.__fec_data._dsg_targets = dsg_targets

    def __gatherer_map_error(self):
        return TypeError(
            "gatherer_map must be a dict((int, int), "
            "DataSpeedUpPacketGatherMachineVertex)")

    def set_gatherer_map(self, gatherer_map):
        """
        Sets the map of x,y to Gatherer Vertices

        :type gatherer_map:
            dict((int, int), DataSpeedUpPacketGatherMachineVertex)
        """
        if not isinstance(gatherer_map, dict):
            raise self.__gatherer_map_error()
        try:
            for (x, y), vertex in gatherer_map.items():
                if not isinstance(x, int):
                    raise self.__gatherer_map_error()
                if not isinstance(y, int):
                    raise self.__gatherer_map_error()
                if not isinstance(
                        vertex, DataSpeedUpPacketGatherMachineVertex):
                    raise self.__gatherer_map_error()
                break  # assume if first is ok all are
        except Exception as ex:  # pylint: disable=broad-except
            raise self.__gatherer_map_error() from ex
        self.__fec_data._gatherer_map = gatherer_map

    def __monitor_map_error(self):
        return TypeError(
            "monitor_map must be a dict((int, int), "
            "ExtraMonitorSupportMachineVertex)")

    def set_monitor_map(self, monitor_map):
        """
        Sets the map of x,y to Monitor Vertices

        :type monitor_map:
            dict((int, int), ExtraMonitorSupportMachineVertex)
        """
        if not isinstance(monitor_map, dict):
            raise self.__monitor_map_error()
        try:
            for (x, y), vertex in monitor_map.items():
                if not isinstance(x, int):
                    raise self.__monitor_map_error()
                if not isinstance(y, int):
                    raise self.__monitor_map_error()
                if not isinstance(vertex, ExtraMonitorSupportMachineVertex):
                    raise self.__monitor_map_error()
                break  # assume if first is ok all are
        except Exception as ex:  # pylint: disable=broad-except
            raise self.__monitor_map_error() from ex
        self.__fec_data._monitor_map = monitor_map
