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
from __future__ import annotations  # Type checking trickery
import logging
import os
from typing import (
    Dict, Iterable, Iterator, Optional, Set, Tuple, Union, List, TYPE_CHECKING)

from spinn_utilities.config_holder import get_report_path
from spinn_utilities.log import FormatAdapter
from spinn_utilities.socket_address import SocketAddress
from spinn_utilities.typing.coords import XY

from spinn_machine import Chip, CoreSubsets, RoutingEntry
from spinnman.data import SpiNNManDataView
from spinnman.model import ExecutableTargets
from spinnman.model.enums import ExecutableType
from spinnman.messages.scp.enums.signal import Signal

from pacman.data import PacmanDataView
from pacman.model.graphs.application import ApplicationEdge, ApplicationVertex
from pacman.model.routing_tables import MulticastRoutingTables

if TYPE_CHECKING:
    # May be circular references in here; it's OK
    from spinn_front_end_common.interface.buffer_management import (
        BufferManager)
    from spinn_front_end_common.interface.java_caller import JavaCaller
    from spinn_front_end_common.utilities.utility_objs import (
        LivePacketGatherParameters)
    from spinn_front_end_common.utility_models import (
        ExtraMonitorSupportMachineVertex,
        DataSpeedUpPacketGatherMachineVertex)
    from spinn_front_end_common.utilities.notification_protocol import (
        NotificationProtocol)
    from spinn_front_end_common.utility_models import LivePacketGather
    from spinn_front_end_common.abstract_models import LiveOutputDevice

logger = FormatAdapter(logging.getLogger(__name__))
_EMPTY_CORE_SUBSETS = CoreSubsets()
hash(_EMPTY_CORE_SUBSETS)


# pylint: disable=protected-access
class _FecDataModel(object):
    """
    Singleton data model.

    This class should not be accessed directly please use the DataView and
    DataWriter classes.
    Accessing or editing the data held here directly is *not supported!*

    There may be other DataModel classes which sit next to this one and hold
    additional data. The DataView and DataWriter classes will combine these
    as needed.

    What data is held where and how can change without notice.
    """

    __singleton = None

    __slots__ = (
        # Data values cached
        "_buffer_manager",
        "_current_run_timesteps",
        "_data_in_multicast_key_to_chip_map",
        "_data_in_multicast_routing_tables",
        "_database_file_path",
        "_database_socket_addresses",
        "_ds_database_path",
        "_executable_targets",
        "_executable_types",
        "_first_machine_time_step",
        "_fixed_routes",
        "_gatherer_map",
        "_hardware_time_step_ms",
        "_hardware_time_step_us",
        "_java_caller",
        "_live_packet_recorder_params",
        "_live_output_vertices",
        "_live_output_devices",
        "_n_run_steps",
        "_next_sync_signal",
        "_next_ds_reference",
        "_none_labelled_edge_count",
        "_notification_protocol",
        "_max_run_time_steps",
        "_monitor_map",
        "_run_step",
        "_simulation_time_step_ms",
        "_simulation_time_step_per_ms",
        "_simulation_time_step_per_s",
        "_simulation_time_step_s",
        "_simulation_time_step_us",
        "_system_multicast_router_timeout_keys",
        "_time_scale_factor")

    def __new__(cls) -> _FecDataModel:
        if cls.__singleton:
            return cls.__singleton
        obj = object.__new__(cls)
        cls.__singleton = obj
        obj._notification_protocol = None
        obj._clear()
        return obj

    def _clear(self) -> None:
        """
        Clears out all data.
        """
        # Can not be cleared during hard reset as previous runs data checked
        self._database_socket_addresses: Set[SocketAddress] = set()
        self._executable_types: Optional[
            Dict[ExecutableType, CoreSubsets]] = None
        self._hardware_time_step_ms: Optional[float] = None
        self._hardware_time_step_us: Optional[int] = None
        self._live_packet_recorder_params: Optional[Dict[
            LivePacketGatherParameters,
            LivePacketGather]] = None
        self._live_output_vertices: Set[Tuple[ApplicationVertex, str]] = set()
        self._live_output_devices: List[LiveOutputDevice] = list()
        self._java_caller: Optional[JavaCaller] = None
        self._none_labelled_edge_count = 0
        self._simulation_time_step_ms: Optional[float] = None
        self._simulation_time_step_per_ms: Optional[float] = None
        self._simulation_time_step_per_s: Optional[float] = None
        self._simulation_time_step_s: Optional[float] = None
        self._simulation_time_step_us: Optional[int] = None
        self._time_scale_factor: Optional[Union[int, float]] = None
        self._hard_reset()

    def _hard_reset(self) -> None:
        """
        Clears out all data that should change after a reset and graph change.
        """
        self._buffer_manager: Optional[BufferManager] = None
        self._data_in_multicast_key_to_chip_map: Optional[Dict[XY, int]] = None
        self._data_in_multicast_routing_tables: Optional[
            MulticastRoutingTables] = None
        self._database_file_path: Optional[str] = None
        self._ds_database_path: Optional[str] = None
        self._next_ds_reference = 0
        self._executable_targets: Optional[ExecutableTargets] = None
        self._fixed_routes: Optional[Dict[XY, RoutingEntry]] = None
        self._gatherer_map: \
            Optional[Dict[Chip, DataSpeedUpPacketGatherMachineVertex]] = None
        self._next_sync_signal: Signal = Signal.SYNC0
        self._notification_protocol: Optional[NotificationProtocol] = None
        self._max_run_time_steps: Optional[int] = None
        self._monitor_map: \
            Optional[Dict[Chip, ExtraMonitorSupportMachineVertex]] = None
        self._system_multicast_router_timeout_keys: Optional[
            Dict[XY, int]] = None
        self._soft_reset()
        self._clear_notification_protocol()

    def _soft_reset(self) -> None:
        """
        Clears timing and other data that should changed every reset.
        """
        self._current_run_timesteps: Optional[int] = 0
        self._first_machine_time_step = 0
        self._run_step: Optional[int] = None
        self._n_run_steps: Optional[int] = None

    def _clear_notification_protocol(self) -> None:
        if self._notification_protocol:
            try:
                self._notification_protocol.close()
            except Exception as ex:  # pylint: disable=broad-except
                logger.exception(
                    f"Error {ex} when closing the notification_protocol "
                    f"ignored")
        self._notification_protocol = None


class FecDataView(PacmanDataView, SpiNNManDataView):
    """
    Adds the extra Methods to the View for spinn_front_end_commom level.

    See :py:class:`~spinn_utilities.data.UtilsDataView` for a more detailed
    description.

    This class is designed to only be used directly within non-PyNN
    repositories as all methods are available to subclasses
    """

    __fec_data = _FecDataModel()

    __slots__ = ()

    # current_run_timesteps and first_machine_time_step

    @classmethod
    def get_current_run_timesteps(cls) -> Optional[int]:
        """
        The end of this or the previous do__run loop time in steps.

        Will be zero if not yet run and not yet in the do_run_loop

        Will be `None` if in run forever mode

        :returns: The end of this or the previous do__run loop time in step
        """
        return cls.__fec_data._current_run_timesteps

    @classmethod
    def get_current_run_time_ms(cls) -> float:
        """
        The end of this or the previous do__run loop time in ms.

        Syntactic sugar for `current_run_timesteps * simulation_time_step_ms`

        Will be zero if not yet run and not yet in the do_run_loop

        Will be zero if in run forever mode

        :returns: The end of this or the previous do__run loop time in ms.
        """
        if cls.__fec_data._current_run_timesteps is None:
            return 0.0
        return (cls.__fec_data._current_run_timesteps *
                cls.get_simulation_time_step_ms())

    # _buffer_manager
    @classmethod
    def has_buffer_manager(cls) -> bool:
        """
        Reports if a BufferManager object has already been set.

        :return:
            True if and only if a BufferManager has been added and not reset
        """
        return cls.__fec_data._buffer_manager is not None

    @classmethod
    def get_buffer_manager(cls) -> BufferManager:
        """
        :returns: the buffer manager if known.
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the buffer manager unavailable
        """
        if cls.__fec_data._buffer_manager is None:
            raise cls._exception("buffer_manager")

        return cls.__fec_data._buffer_manager

    @classmethod
    def get_first_machine_time_step(cls) -> int:
        """
        :returns: The start of this or the next do_run loop time in steps.
        """
        return cls.__fec_data._first_machine_time_step

    # max_run_time_steps methods

    @classmethod
    def get_max_run_time_steps(cls) -> int:
        """
        Returns the calculated longest time this or a future run loop could be.

        Mainly used to indicate the number of timesteps the vertex can and
        therefore should reserve memory for

        Guaranteed to be positive int if available

        :returns: The longest run possible without using auto pause resume
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the max run time is currently unavailable
        """
        if cls.__fec_data._max_run_time_steps is None:
            raise cls._exception("max_run_time_steps")

        return cls.__fec_data._max_run_time_steps

    @classmethod
    def has_max_run_time_steps(cls) -> bool:
        """
        :returns: True if max_run_time_steps is currently available.
        """
        return cls.__fec_data._max_run_time_steps is not None

    # simulation_time_step_methods

    @classmethod
    def has_time_step(cls) -> bool:
        """
        Check if any/all of the time_step values are known.

        True When all simulation/hardware_time_step methods are known
        False when none of the simulation/hardware_time_step values are known.
        There is never a case when some are known and others not

        :returns: True if any of the time_step values are known
        """
        return cls.__fec_data._simulation_time_step_us is not None

    @classmethod
    def get_simulation_time_step_us(cls) -> int:
        """
        The simulation timestep, in microseconds.

        Previously known as "machine_time_step"

        :returns: The simulation timestep in microseconds.
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the simulation_time_step_us is currently unavailable
        """
        if cls.__fec_data._simulation_time_step_us is None:
            raise cls._exception("simulation_time_step_us")
        return cls.__fec_data._simulation_time_step_us

    @classmethod
    def get_simulation_time_step_s(cls) -> float:
        """
        The simulation timestep, in seconds.

        Syntactic sugar for `simulation_time_step() / 1,000,000`.

        :returns: The simulation timestep, in seconds.
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the simulation_time_step_ms is currently unavailable
        """
        if cls.__fec_data._simulation_time_step_s is None:
            raise cls._exception("simulation_time_step_s")
        return cls.__fec_data._simulation_time_step_s

    @classmethod
    def get_simulation_time_step_ms(cls) -> float:
        """
        The simulation time step, in milliseconds.

        Syntactic sugar for `simulation_time_step_us / 1000`.

        :returns: The simulation time step, in milliseconds.
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the simulation_time_step_ms is currently unavailable
        """
        if cls.__fec_data._simulation_time_step_ms is None:
            raise cls._exception("simulation_time_step_ms")
        return cls.__fec_data._simulation_time_step_ms

    @classmethod
    def get_simulation_time_step_per_ms(cls) -> float:
        """
        The number of simulation time steps in a millisecond.

        Syntactic sugar for `1000 / simulation_time_step_us`

        :returns: The number of simulation time steps in a millisecond.
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the simulation_time_step is currently unavailable
        """
        if cls.__fec_data._simulation_time_step_per_ms is None:
            raise cls._exception("simulation_time_step_per_ms")
        return cls.__fec_data._simulation_time_step_per_ms

    @classmethod
    def get_simulation_time_step_per_s(cls) -> float:
        """
        The number of simulation time steps in a seconds.

        Syntactic sugar for `1,000,000 / simulation_time_step_us`

        :returns: The number of simulation time steps in a seconds.
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the simulation_time_step is currently unavailable
        """
        if cls.__fec_data._simulation_time_step_per_s is None:
            raise cls._exception("simulation_time_step_per_s")
        return cls.__fec_data._simulation_time_step_per_s

    @classmethod
    def get_hardware_time_step_ms(cls) -> float:
        """
        The hardware timestep, in milliseconds.

        Syntactic sugar for `simulation_time_step_ms * time_scale_factor`

        :returns: The hardware timestep, in milliseconds.
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the hardware_time_step is currently unavailable
        """
        if cls.__fec_data._hardware_time_step_ms is None:
            raise cls._exception("hardware_time_step_ms")
        return cls.__fec_data._hardware_time_step_ms

    @classmethod
    def get_hardware_time_step_us(cls) -> int:
        """
        The hardware timestep, in microseconds.

        Syntactic sugar for `simulation_time_step_us * time_scale_factor`

        :returns: The hardware timestep, in microseconds.
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the hardware_time_step is currently unavailable
        """
        if cls.__fec_data._hardware_time_step_us is None:
            raise cls._exception("hardware_time_step_us")
        return cls.__fec_data._hardware_time_step_us

    # time scale factor

    @classmethod
    def get_time_scale_factor(cls) -> Union[int, float]:
        """
        :returns: The timescale factor
        :raises SpiNNUtilsException:
            If the time_scale_factor is currently unavailable
        :raises SpiNNUtilsException:
            If the time_scale_factor is currently unavailable
        """
        if cls.__fec_data._time_scale_factor is None:
            raise cls._exception("time_scale_factor")
        return cls.__fec_data._time_scale_factor

    @classmethod
    def has_time_scale_factor(cls) -> bool:
        """
        :returns: True if the time_scale_factor is currently available
        """
        return cls.__fec_data._time_scale_factor is not None

    @classmethod
    def get_run_step(cls) -> Optional[int]:
        """
        Get the auto pause and resume step currently running if any.

        If and only if currently in an auto pause and resume loop this will
        report the number of the step. Starting at 1

        In most cases this will return `None`, including when running without
        steps.

        :returns: None or the run_step if current auto pause loop number
        """
        return cls.__fec_data._run_step

    @classmethod
    def is_last_step(cls) -> bool:
        """
        Detects if this is the last or only step of this run.

        When not using auto pause resume steps this always returns True

        When running forever with steps this always returns False.

        For auto pause steps of a fixed run time this returns True
        only on the last of these steps.

        :returns: True unless in any but the last auto loop run
        """
        if cls.__fec_data._n_run_steps is None:
            return cls.__fec_data._run_step is None
        else:
            return cls.__fec_data._run_step == cls.__fec_data._n_run_steps

    # system multicast routing data

    @classmethod
    def get_data_in_multicast_key_to_chip_map(cls) -> Dict[XY, int]:
        """
        Retrieve the data_in_multicast_key_to_chip_map if known.
        Keys are the coordinates of chips.
        Values are the base keys for multicast communication
        received by the Data In streaming module
        of the extra monitor running on those chips.

        :returns: Map of Chip XY to multicast key
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the data_in_multicast_key_to_chip_map is currently unavailable
        """
        if cls.__fec_data._data_in_multicast_key_to_chip_map is None:
            raise cls._exception("data_in_multicast_key_to_chip_map")
        return cls.__fec_data._data_in_multicast_key_to_chip_map

    @classmethod
    def get_data_in_multicast_routing_tables(cls) -> MulticastRoutingTables:
        """
        Retrieve the data_in_multicast_routing_tables if known.
        These are the routing tables used to handle Data In streaming.

        :returns: Routing tables to use for data in
        :raises SpiNNUtilsException:
            If the data_in_multicast_routing_tables is currently unavailable
        """
        if cls.__fec_data._data_in_multicast_routing_tables is None:
            raise cls._exception("data_in_multicast_routing_tables")
        return cls.__fec_data._data_in_multicast_routing_tables

    @classmethod
    def get_system_multicast_router_timeout_keys(cls) -> Dict[XY, int]:
        """
        Retrieve the system_multicast_router_timeout_keys if known.
        Keys are the coordinates of chips.
        Values are the base keys for multicast communications received by the
        re-injector module of the extra monitor running on those chips.

        :returns: Mapping of Chip XY to multicast keys
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the system_multicast_router_timeout_keys is currently
            unavailable
        """
        if cls.__fec_data._system_multicast_router_timeout_keys is None:
            raise cls._exception("system_multicast_router_timeout_keys")
        return cls.__fec_data._system_multicast_router_timeout_keys

    # fixed_routes
    @classmethod
    def has_fixed_routes(cls) -> bool:
        """
        Detects if fixed routes have been created.

        :return:  True if the fixed route have been created
        """
        return cls.__fec_data._fixed_routes is not None

    @classmethod
    def get_fixed_routes(cls) -> Dict[XY, RoutingEntry]:
        """
        Gets the fixed routes if they have been created.

        :returns: mapping of Chip coordinates to their routing entry
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the fixed_routes is currently unavailable
        """
        if cls.__fec_data._fixed_routes is None:
            raise cls._exception("fixed_routes")
        return cls.__fec_data._fixed_routes

    @classmethod
    def has_java_caller(cls) -> bool:
        """
        Reports if there is a Java called that can be used.

        Equivalent to `get_config_bool("Java", "use_java")` as the writer will
        have created the caller during setup

        The behaviour when Mocked is currently to always return False.

        :returns: True if Java should be used/ get_java_caller will work.
        """
        return cls.__fec_data._java_caller is not None

    @classmethod
    def get_java_caller(cls) -> JavaCaller:
        """
        :returns: The Java_caller.
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the java_caller is currently unavailable
        """
        if cls.__fec_data._java_caller is None:
            raise cls._exception("java_caller")
        return cls.__fec_data._java_caller

    # run_dir_path in UtilsDataView

    @classmethod
    def get_app_provenance_dir_path(cls) -> str:
        """
        Returns the path to the directory that holds all application provenance
        files.

        This will be the path used by the last run call or to be used by
        the next run if it has not yet been called.

        .. note::
            In unit-test mode this returns a temporary directory
            shared by all path methods.

        :returns:  The path to the directory that holds
           all application provenance files.
        :raises ~spinn_utilities.exceptions.SimulatorNotSetupException:
            If the simulator has not been setup
        """
        if cls._is_mocked():
            return cls._temporary_dir_path()

        return get_report_path("path_iobuf_app", is_dir=True)

    @classmethod
    def get_system_provenance_dir_path(cls) -> str:
        """
        Returns the path to the directory that holds system provenance files.

        This will be the path used by the last run call or to be used by
        the next run if it has not yet been called.

        .. note::
            In unit-test mode this returns a temporary directory
            shared by all path methods.

        :returns: the path to the directory that holds system provenance file
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the simulation_time_step is currently unavailable
        """
        if cls._is_mocked():
            return cls._temporary_dir_path()
        return get_report_path("path_iobuf_system", is_dir=True)

    @classmethod
    def get_next_none_labelled_edge_number(cls) -> int:
        """
        :returns: an unused number for labelling an unlabelled edge.
        """
        cls.__fec_data._none_labelled_edge_count += 1
        return cls.__fec_data._none_labelled_edge_count

    @classmethod
    def get_next_sync_signal(cls) -> Signal:
        """
        :returns: alternately Signal.SYNC0 and Signal.SYNC1.
        """
        if cls.__fec_data._next_sync_signal == Signal.SYNC0:
            cls.__fec_data._next_sync_signal = Signal.SYNC1
            return Signal.SYNC0
        else:
            cls.__fec_data._next_sync_signal = Signal.SYNC0
            return Signal.SYNC1

    @classmethod
    def get_executable_types(cls) -> Dict[ExecutableType, CoreSubsets]:
        """
        Gets the executable_types if they have been created.

        :returns: Mapping of used types to the cores they are on
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the executable_types is currently unavailable
        """
        if cls.__fec_data._executable_types is None:
            raise cls._exception("executable_types")
        return cls.__fec_data._executable_types

    @classmethod
    def get_cores_for_type(
            cls, executable_type: ExecutableType) -> CoreSubsets:
        """
        :param executable_type: Type to filter for
        :returns: The subset of cores running executables of the given type.
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the executable_types is currently unavailable
        """
        return cls.get_executable_types().get(
            executable_type, _EMPTY_CORE_SUBSETS)

    @classmethod
    def has_live_packet_recorder_params(cls) -> bool:
        """
        Reports if there are live_packet_recorder_params.

        If True the live_packet_recorder_params not be empty

        :returns: True if there is at least one LivePacketGather known
        """
        # The live_packet_recorder_params is None until one is added
        return cls.__fec_data._live_packet_recorder_params is not None

    @classmethod
    def get_live_packet_recorder_params(cls) -> Dict[
            LivePacketGatherParameters, LivePacketGather]:
        """
        :returns: Mapping of live_packet_gatherer_params to a list of tuples
        (vertex and list of ids)).

        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the _live_packet_recorder_params is currently unavailable
        """
        if cls.__fec_data._live_packet_recorder_params is None:
            raise cls._exception("live_packet_recorder_params")
        return cls.__fec_data._live_packet_recorder_params

    # Add method in view so add can be done without going through ASB
    @classmethod
    def add_live_packet_gatherer_parameters(
            cls, live_packet_gatherer_params: LivePacketGatherParameters,
            vertex_to_record_from: ApplicationVertex,
            partition_ids: Iterable[str]) -> None:
        """
        Adds parameters for a new live packet gatherer (LPG) if needed, or
        adds to the tracker for parameters.

        .. note::
            If the
            :py:class:`~pacman.model.graphs.application.ApplicationGraph`
            is used, the vertex must be an
            :py:class:`~pacman.model.graphs.application.ApplicationVertex`.
            If not, it must be a
            :py:class:`~pacman.model.graphs.machine.MachineVertex`.

        :param live_packet_gatherer_params:
            parameters for an LPG to look for or create
        :param vertex_to_record_from:
            the vertex that needs to send to a given LPG
        :param partition_ids:
            the IDs of the partitions to connect from the vertex;
            can also be a single string (strings are iterable)
        """
        if cls.__fec_data._live_packet_recorder_params is None:
            cls.__fec_data._live_packet_recorder_params = dict()
        lpg_vertex = cls.__fec_data._live_packet_recorder_params.get(
            live_packet_gatherer_params)
        if lpg_vertex is None:
            # pylint: disable=import-outside-toplevel
            # UGLY import due to circular reference
            from spinn_front_end_common.utility_models import (
                LivePacketGather as LPG)
            lpg_vertex = LPG(
                live_packet_gatherer_params, live_packet_gatherer_params.label)
            cls.__fec_data._live_packet_recorder_params[
                live_packet_gatherer_params] = lpg_vertex
            cls.add_vertex(lpg_vertex)
        if isinstance(partition_ids, str):
            cls.add_edge(
                ApplicationEdge(vertex_to_record_from, lpg_vertex),
                partition_ids)
        else:
            for part_id in partition_ids:
                cls.add_edge(
                    ApplicationEdge(vertex_to_record_from, lpg_vertex),
                    part_id)

    @classmethod
    def get_database_file_path(cls) -> Optional[str]:
        """
        :returns: The database_file_path if set or `None` if not set
            or set to `None`
        """
        return cls.__fec_data._database_file_path

    @classmethod
    def get_executable_targets(cls) -> ExecutableTargets:
        """
        :returns: Binaries to be executed.
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the executable_targets is currently unavailable
        """
        if cls.__fec_data._executable_targets is None:
            raise cls._exception("executable_targets")
        return cls.__fec_data._executable_targets

    @classmethod
    def get_ds_database_path(cls) -> str:
        """
        :returns: The path for the Data Spec database.
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the ds_database path is currently unavailable
        """
        if cls.__fec_data._ds_database_path is None:
            if cls._is_mocked():
                return os.path.join(cls._temporary_dir_path(), "ds.sqlite3")
            raise cls._exception("_ds_database+path")
        return cls.__fec_data._ds_database_path

    @classmethod
    def has_monitors(cls) -> bool:
        """
        Detect is ExtraMonitorSupportMachineVertex(s) have been created.

        :returns: True if the monitors exist, False otherwise.
        """
        return cls.__fec_data._monitor_map is not None

    @classmethod
    def get_monitor_by_xy(
            cls, x: int, y: int) -> ExtraMonitorSupportMachineVertex:
        """
        :param x: X coordinate of chip
        :param y: Y coordinate of chip
        :returns: The ExtraMonitorSupportMachineVertex for chip (x,y).
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the monitors are currently unavailable
        :raises KeyError: If chip (x,y) does not have a monitor
        """
        if cls.__fec_data._monitor_map is None:
            raise cls._exception("monitors_map")
        return cls.__fec_data._monitor_map[cls.get_chip_at(x, y)]

    @classmethod
    def get_monitor_by_chip(
            cls, chip: Chip) -> ExtraMonitorSupportMachineVertex:
        """
        :param chip: chip to get monitor for
        :returns: The ExtraMonitorSupportMachineVertex for chip.
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the monitors are currently unavailable
        :raises KeyError: If chip does not have a monitor
        """
        if cls.__fec_data._monitor_map is None:
            raise cls._exception("monitors_map")
        return cls.__fec_data._monitor_map[chip]

    @classmethod
    def iterate_monitor_items(cls) -> \
            Iterable[Tuple[Chip, ExtraMonitorSupportMachineVertex]]:
        """
        Iterates over the Chip and ExtraMonitorSupportMachineVertex.

        get_n_monitors returns the number of items this iterable will provide.

        :returns: Iterator of a tuple of Chip and its monitor
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the monitors are currently unavailable
        """
        if cls.__fec_data._monitor_map is None:
            raise cls._exception("monitors_map")
        return cls.__fec_data._monitor_map.items()

    @classmethod
    def get_n_monitors(cls) -> int:
        """
        Number of ExtraMonitorSupportMachineVertexs.

        This is the total number of monitors NOT the number per chip.

        :returns: Number of monitors for the whole Machine
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the monitors are currently unavailable
        """
        if cls.__fec_data._monitor_map is None:
            raise cls._exception("monitors_map")
        return len(cls.__fec_data._monitor_map)

    @classmethod
    def iterate_monitors(cls) -> Iterable[ExtraMonitorSupportMachineVertex]:
        """
        :returns: Iterator over the ExtraMonitorSupportMachineVertex(s).
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the monitors are currently unavailable
        """
        if cls.__fec_data._monitor_map is None:
            raise cls._exception("monitors_map")
        return cls.__fec_data._monitor_map.values()

    @classmethod
    def get_gatherer_by_chip(
            cls, chip: Chip) -> DataSpeedUpPacketGatherMachineVertex:
        """
        :param chip: The Ethernet-enabled chip
        :returns:
            The DataSpeedUpPacketGatherMachineVertex
            for an Ethernet-enabled chip.
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the gatherers are currently unavailable
        :raises KeyError:
            If the chip does not have a gatherer
            (e.g., if it is not an Ethernet-enabled chip)
        """
        if cls.__fec_data._gatherer_map is None:
            raise cls._exception("gatherer_map")
        return cls.__fec_data._gatherer_map[chip]

    @classmethod
    def get_gatherer_by_xy(
            cls, x: int, y: int) -> DataSpeedUpPacketGatherMachineVertex:
        """
        :param x: X coordinate of chip
        :param y: Y coordinate of chip
        :returns: The DataSpeedUpPacketGatherMachineVertex for chip (x,y).
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the gatherers are currently unavailable
        :raises KeyError: If chip (x,y) does not have a monitor
        """
        if cls.__fec_data._gatherer_map is None:
            raise cls._exception("gatherer_map")
        return cls.__fec_data._gatherer_map[cls.get_chip_at(x, y)]

    @classmethod
    def iterate_gather_items(cls) -> Iterable[
            Tuple[Chip, DataSpeedUpPacketGatherMachineVertex]]:
        """
        Iterates over the Chip and DataSpeedUpPacketGatherMachineVertex.

        get_n_gathers returns the number of items this iterable will provide

        :returns: Iterator over tuple of Chip and its gatherer
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the gathers are currently unavailable
        """
        if cls.__fec_data._gatherer_map is None:
            raise cls._exception("gatherer_map")
        return cls.__fec_data._gatherer_map.items()

    @classmethod
    def get_n_gathers(cls) -> int:
        """
        Number of DataSpeedUpPacketGatherMachineVertex(s).

        This is the total number of gathers NOT the number per chip

        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the gathers are currently unavailable
        :returns: Total number of gathers in the whole Machine.
        """
        if cls.__fec_data._gatherer_map is None:
            raise cls._exception("gatherer_map")
        return len(cls.__fec_data._gatherer_map)

    @classmethod
    def iterate_gathers(cls) -> Iterable[DataSpeedUpPacketGatherMachineVertex]:
        """
        :returns: Iterator over the DataSpeedUpPacketGatherMachineVertex(s).
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the gathers are currently unavailable
        """
        if cls.__fec_data._gatherer_map is None:
            raise cls._exception("gatherer_map")
        return cls.__fec_data._gatherer_map.values()

    @classmethod
    def iterate_database_socket_addresses(cls) -> Iterator[SocketAddress]:
        """
        :returns: Iterator over the registered database_socket_addresses.
        """
        return iter(cls.__fec_data._database_socket_addresses)

    @classmethod
    def get_n_database_socket_addresses(cls) -> int:
        """
        :returns: Number of registered database_socket_addresses.
        """
        return len(cls.__fec_data._database_socket_addresses)

    @classmethod
    def add_database_socket_address(
            cls, database_socket_address: SocketAddress) -> None:
        """
        Adds a socket address to the list of known addresses.

        :param database_socket_address:
        :raises TypeError: if database_socket_address is not a SocketAddress
        """
        if not isinstance(database_socket_address, SocketAddress):
            raise TypeError("database_socket_address must be a SocketAddress")
        cls.__fec_data._database_socket_addresses.add(database_socket_address)

    @classmethod
    def add_database_socket_addresses(
            cls, database_socket_addresses: Optional[Iterable[SocketAddress]]
            ) -> None:
        """
        Adds all socket addresses to the list of known addresses.

        :param database_socket_addresses: The addresses to add
        :raises TypeError:
           if database_socket_address is not a iterable of `SocketAddress`
        """
        if database_socket_addresses is None:
            return
        for socket_address in database_socket_addresses:
            cls.add_database_socket_address(socket_address)

    @classmethod
    def get_notification_protocol(cls) -> NotificationProtocol:
        """
        :returns: The notification protocol handler.
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the notification_protocol is currently unavailable
        """
        if cls.__fec_data._notification_protocol is None:
            raise cls._exception("notification_protocol")
        return cls.__fec_data._notification_protocol

    @classmethod
    def add_live_output_vertex(
            cls, vertex: ApplicationVertex, partition_id: str) -> None:
        """
        Add a vertex that is to be output live, and so wants its atom IDs
        recorded in the database.

        :param vertex: The vertex to add
        :param partition_id: The partition to get the IDs of
        """
        if not isinstance(vertex, ApplicationVertex):
            raise NotImplementedError(
                "You only need to add ApplicationVertices")
        cls.__fec_data._live_output_vertices.add((vertex, partition_id))

    @classmethod
    def iterate_live_output_vertices(
            cls) -> Iterable[Tuple[ApplicationVertex, str]]:
        """
        :returns:
           An iterator over the live output vertices and partition IDs.
        """
        return iter(cls.__fec_data._live_output_vertices)

    @classmethod
    def get_next_ds_references(cls, number: int) -> List[int]:
        """
        Get a list of unique data specification references

        These will be unique since the last hard reset

        :param number: number of values in the list
        :returns: List of unique references numbers
        """
        references = range(cls.__fec_data._next_ds_reference,
                           cls.__fec_data._next_ds_reference+number)
        cls.__fec_data._next_ds_reference += number
        return list(references)

    @classmethod
    def add_live_output_device(cls, device: LiveOutputDevice) -> None:
        """
        Add a live output device.

        :param device: The device to be added
        """
        cls.__fec_data._live_output_devices.append(device)

    @classmethod
    def iterate_live_output_devices(cls) -> Iterable[LiveOutputDevice]:
        """
        :returns: Iterator over live output devices.
        """
        return iter(cls.__fec_data._live_output_devices)
