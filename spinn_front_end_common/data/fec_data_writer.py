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


import logging
import os
from typing import Dict, Optional, Tuple

from spinn_utilities.config_holder import (
    get_config_int, get_config_int_or_none)
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spinn_utilities.typing.coords import XY

from spinn_machine import Chip, CoreSubsets, RoutingEntry

from spinnman.data.spinnman_data_writer import SpiNNManDataWriter
from spinnman.messages.scp.enums.signal import Signal
from spinnman.model import ExecutableTargets
from spinnman.model.enums import ExecutableType
from pacman.data.pacman_data_writer import PacmanDataWriter
from pacman.model.routing_tables import MulticastRoutingTables
from pacman.model.graphs.application import ApplicationVertex
from spinn_front_end_common.utilities.notification_protocol import (
    NotificationProtocol)
from spinn_front_end_common.interface.buffer_management import BufferManager
from spinn_front_end_common.interface.java_caller import JavaCaller
from spinn_front_end_common.utilities.constants import (
    MICRO_TO_MILLISECOND_CONVERSION, MICRO_TO_SECOND_CONVERSION)
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utility_models import (
    DataSpeedUpPacketGatherMachineVertex, ExtraMonitorSupportMachineVertex)

from .fec_data_view import FecDataView, _FecDataModel

logger = FormatAdapter(logging.getLogger(__name__))
__temp_dir = None


class FecDataWriter(PacmanDataWriter, SpiNNManDataWriter, FecDataView):
    """
    See :py:class:`~spinn_utilities.data.utils_data_writer.UtilsDataWriter`.

    This class is designed to only be used directly by
    :py:class:`AbstractSpinnakerBase`
    and within the Non-PyNN repositories unit tests as all methods are
    available to subclasses.
    """
    __fec_data = _FecDataModel()
    __slots__ = ()
    # pylint: disable=protected-access

    @overrides(PacmanDataWriter._mock)
    def _mock(self) -> None:
        PacmanDataWriter._mock(self)
        self._spinnman_mock()
        self.__fec_data._clear()
        self.set_up_timings(1000, 1)

    @overrides(PacmanDataWriter._setup)
    def _setup(self) -> None:
        PacmanDataWriter._setup(self)
        self._spinnman_setup()
        self.__fec_data._clear()

    @overrides(PacmanDataWriter._hard_reset)
    def _hard_reset(self) -> None:
        PacmanDataWriter._hard_reset(self)
        SpiNNManDataWriter._local_hard_reset(self)
        self.__fec_data._hard_reset()

    @overrides(PacmanDataWriter._soft_reset)
    def _soft_reset(self) -> None:
        PacmanDataWriter._soft_reset(self)
        SpiNNManDataWriter._local_soft_reset(self)
        self.__fec_data._soft_reset()

    def set_buffer_manager(self, buffer_manager: BufferManager) -> None:
        """
        Sets the Buffer manager variable.

        :param buffer_manager:
        """
        if not isinstance(buffer_manager, BufferManager):
            raise TypeError("buffer_manager must be a BufferManager")
        self.__fec_data._buffer_manager = buffer_manager

    def increment_current_run_timesteps(
            self, increment: Optional[int]) -> None:
        """
        Increment the current_run_timesteps and sets first_machine_time_step.

        A `None` increment signals run_forever

        :param increment: The timesteps for this do_run loop
        """
        if self.__fec_data._current_run_timesteps is None:
            raise NotImplementedError("Run after run until stopped")
        self.__fec_data._first_machine_time_step = \
            self.__fec_data._current_run_timesteps

        if increment is None:
            self.__fec_data._current_run_timesteps = None
        elif isinstance(increment, int):
            if increment < 0:
                raise ConfigurationException(
                    f"increment {increment} must not be negative")
            self.__fec_data._current_run_timesteps += increment
        else:
            raise TypeError("increment should be an int (or None")

    def set_current_run_timesteps(self, current_run_timesteps: int) -> None:
        """
        Allows the end of a run forever to set the runtime read from the cores

        :param current_run_timesteps:
        """
        if self.__fec_data._current_run_timesteps is not None:
            raise NotImplementedError(
                "Can only be called once after a run forever")
        first = self.__fec_data._first_machine_time_step
        if first > current_run_timesteps:
            raise NotImplementedError(
                f"Time does not go backwards! "
                f"{first=} > {current_run_timesteps=}")
        if first + self.get_max_run_time_steps() < current_run_timesteps:
            logger.warning(
                "Last run was longer than duration supported by recording")
        self.__fec_data._current_run_timesteps = current_run_timesteps

    def set_max_run_time_steps(self, max_run_time_steps: int) -> None:
        """
        Sets the max_run_time_steps value

        :param max_run_time_steps: new value
        """
        if not isinstance(max_run_time_steps, int):
            raise TypeError("max_run_time_steps should be an int")
        if max_run_time_steps <= 0:
            raise ConfigurationException(
                f"max_run_time_steps {max_run_time_steps} must be positive")
        self.__fec_data._max_run_time_steps = max_run_time_steps

    def set_up_timings(
            self, simulation_time_step_us: Optional[int],
            time_scale_factor: Optional[float],
            default_time_scale_factor: float = 1.0) -> None:
        """
        Set up timings for the simulation.

        :param simulation_time_step_us:
            An explicitly specified time step for the simulation in .
            If `None`, the value is read from the configuration
        :param time_scale_factor:
            An explicitly specified time scale factor for the simulation.
            If `None`, the value is read from the configuration
        :param default_time_scale_factor:
            A back up time scale factor for the simulation.
            Only used if time_scale_factor parameter and configuration are
            both `None`, by default this is 1.0.
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

    def _set_simulation_time_step(
            self, simulation_time_step_us: Optional[int]) -> None:
        """
        :param simulation_time_step_us:
            An explicitly specified time step for the simulation.  If `None`,
            the value is read from the configuration
        """
        if simulation_time_step_us is None:
            simulation_time_step_us = get_config_int(
                "Machine", "simulation_time_step")

        if not isinstance(simulation_time_step_us, int):
            raise TypeError("simulation_time_step_us should be an int")

        if simulation_time_step_us <= 0:
            raise ConfigurationException(
                f'invalid simulation_time_step {simulation_time_step_us}'
                ': must greater than zero')

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
            self, time_scale_factor: Optional[float],
            default_time_scale_factor: float) -> None:
        """
        Set up time_scale_factor.

        If time_scale_factor is provide that is used

        Then if configuration is not `None` that is used

        Otherwise the default is used

        :param time_scale_factor:
            An explicitly specified time scale factor for the simulation.
            If `None`, the value is read from the configuration
        """
        if time_scale_factor is None:
            # Note while this reads from the cfg the cfg default is None
            time_scale_factor = get_config_int_or_none(
                "Machine", "time_scale_factor")

        if time_scale_factor is None:
            if default_time_scale_factor is not None:
                time_scale_factor = default_time_scale_factor

        if not isinstance(time_scale_factor, (int, float)):
            raise TypeError("time_scale_factor should be an int (or float)")

        if time_scale_factor <= 0:
            raise ConfigurationException(
                f'invalid time_scale_factor {time_scale_factor}'
                ': must greater than zero')

        self.__fec_data._time_scale_factor = time_scale_factor

    def _set_hardware_timestep(self) -> None:
        raw = (self.get_simulation_time_step_us() *
               self.get_time_scale_factor())
        rounded = round(raw)
        if abs(rounded - raw) > 0.0001:
            raise ConfigurationException(
                "The multiplication of simulation time step in microseconds: "
                f"{self.get_simulation_time_step_us()} and times scale factor"
                f": {self.get_time_scale_factor()} produced a non integer "
                f"hardware time step of {raw}")

        logger.info(
            "Setting hardware timestep as {} microseconds based on "
            "simulation time step of {} and timescale factor of {}",
            rounded, self.get_simulation_time_step_us(),
            self.get_time_scale_factor())
        self.__fec_data._hardware_time_step_us = rounded
        self.__fec_data._hardware_time_step_ms = (
            rounded / MICRO_TO_MILLISECOND_CONVERSION)

    def set_system_multicast_routing_data(
            self, data: Tuple[
                MulticastRoutingTables, Dict[XY, int], Dict[XY, int]]) -> None:
        """
        Sets the system_multicast_routing_data.

        These are: `data_in_multicast_routing_tables`,
        `data_in_multicast_key_to_chip_map`,
        `system_multicast_router_timeout_keys`

        :param data: new value
        """
        routing_tables, key_to_chip_map, timeout_keys = data
        if not isinstance(routing_tables, MulticastRoutingTables):
            raise TypeError("First element must be a MulticastRoutingTables")
        if not isinstance(key_to_chip_map, dict):
            raise TypeError("Second element must be dict")
        if not isinstance(timeout_keys, dict):
            raise TypeError("Third element must be a dict")
        self.__fec_data._data_in_multicast_key_to_chip_map = key_to_chip_map
        self.__fec_data._data_in_multicast_routing_tables = routing_tables
        self.__fec_data._system_multicast_router_timeout_keys = timeout_keys

    def set_fixed_routes(
            self, fixed_routes: Dict[Tuple[int, int], RoutingEntry]) -> None:
        """
        Sets the routes.

        :param fixed_routes:
        """
        if not isinstance(fixed_routes, dict):
            raise TypeError("fixed_routes must be a dict")
        self.__fec_data._fixed_routes = fixed_routes

    def set_java_caller(self, java_caller: JavaCaller) -> None:
        """
        Sets/ overwrites the method to call Java

        :param java_caller:
        """
        if not isinstance(java_caller, JavaCaller):
            raise TypeError("java_caller must be a JavaCaller")
        self.__fec_data._java_caller = java_caller

    def reset_sync_signal(self) -> None:
        """
        Returns the sync signal to the default value.
        """
        self.__fec_data._next_sync_signal = Signal.SYNC0

    def set_executable_types(self, executable_types: Dict[
            ExecutableType, CoreSubsets]) -> None:
        """
        Sets/ overwrites the executable types

        :param executable_types:
        """
        if not isinstance(executable_types, dict):
            raise TypeError("executable_types must be a Dict")
        self.__fec_data._executable_types = executable_types

    def set_database_file_path(
            self, database_file_path: Optional[str]) -> None:
        """
        Sets the database_file_path variable. Possibly to `None`.

        :param database_file_path:
        """
        if not isinstance(database_file_path, (str, type(None))):
            raise TypeError("database_file_path must be a str or None")
        self.__fec_data._database_file_path = database_file_path

    def set_executable_targets(
            self, executable_targets: ExecutableTargets) -> None:
        """
        Sets the executable_targets

        :param executable_targets:
        """
        if not isinstance(executable_targets, ExecutableTargets):
            raise TypeError("executable_targets must be a ExecutableTargets")
        self.__fec_data._executable_targets = executable_targets

    def set_ds_database_path(self, ds_database_path: str) -> None:
        """
        Sets the Data Spec targets database.

        :param ds_database_path: Existing path to the database
        """
        if not os.path.isfile(ds_database_path):
            raise TypeError("ds_database path must be a filee")

        self.__fec_data._ds_database_path = ds_database_path

    def __gatherer_map_error(self) -> TypeError:
        return TypeError(
            "gatherer_map must be a dict(Chip, "
            "DataSpeedUpPacketGatherMachineVertex)")

    def set_gatherer_map(self, gatherer_map: Dict[
            Chip, DataSpeedUpPacketGatherMachineVertex]) -> None:
        """
        Sets the map of Chip to Gatherer Vertices.

        :param gatherer_map:
        """
        if not isinstance(gatherer_map, dict):
            raise self.__gatherer_map_error()
        try:
            for chip, vertex in gatherer_map.items():
                if not isinstance(chip, Chip):
                    raise self.__gatherer_map_error()
                if not isinstance(
                        vertex, DataSpeedUpPacketGatherMachineVertex):
                    raise self.__gatherer_map_error()
                break  # assume if first is OK all are
        except Exception as ex:  # pylint: disable=broad-except
            raise self.__gatherer_map_error() from ex
        self.__fec_data._gatherer_map = gatherer_map

    def __monitor_map_error(self) -> TypeError:
        return TypeError(
            "monitor_map must be a dict(Chip, "
            "ExtraMonitorSupportMachineVertex)")

    def set_monitor_map(self, monitor_map: Dict[
            Chip, ExtraMonitorSupportMachineVertex]) -> None:
        """
        Sets the map of Chip to Monitor Vertices.

        :param monitor_map:
        """
        if not isinstance(monitor_map, dict):
            raise self.__monitor_map_error()
        try:
            for chip, vertex in monitor_map.items():
                if not isinstance(chip, Chip):
                    raise self.__monitor_map_error()
                if not isinstance(vertex, ExtraMonitorSupportMachineVertex):
                    raise self.__monitor_map_error()
                break  # assume if first is OK all are
        except TypeError:
            raise
        except Exception as ex:  # pylint: disable=broad-except
            raise self.__monitor_map_error() from ex
        self.__fec_data._monitor_map = monitor_map

    def set_notification_protocol(
            self, notification_protocol: NotificationProtocol) -> None:
        """
        Sets the notification_protocol.
        """
        self.__fec_data._clear_notification_protocol()
        if not isinstance(notification_protocol, NotificationProtocol):
            raise TypeError(
                "notification_protocol must be a NotificationProtocol")
        self.__fec_data._notification_protocol = notification_protocol

    def clear_notification_protocol(self) -> None:
        """
        Closes an existing notification_protocol and sets the value to `None`.

        If no notification_protocol exist this method silently returns.

        If the close causes an Exception it is logged and ignored
        """
        self.__fec_data._clear_notification_protocol()

    @classmethod
    @overrides(FecDataView.add_vertex)
    def add_vertex(cls, vertex: ApplicationVertex) -> None:
        # Avoid the safety check in FecDataView
        PacmanDataWriter.add_vertex(vertex)

    def set_n_run_steps(self, n_run_steps: int) -> None:
        """
        Sets the number of expected run-steps

        Only used for auto pause resume and not running forever

        :param n_run_steps:
        """
        self.__fec_data._n_run_steps = n_run_steps

    def next_run_step(self) -> int:
        """
        Starts or increases the run step count.

        Run steps start at 1

        :return: The next step number
        """
        if self.__fec_data._run_step is None:
            self.__fec_data._run_step = 1
            return 1
        self.__fec_data._run_step += 1
        return self.__fec_data._run_step

    def clear_run_steps(self) -> None:
        """
        Clears the run step.

        get_run_step will go back to returning `None`

        next_run_step will restart at 1
        """
        self.__fec_data._run_step = None
        self.__fec_data._n_run_steps = None
