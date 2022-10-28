# Copyright (c) 2021-2022 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the impl`ied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import os
from spinn_utilities.log import FormatAdapter
from spinn_utilities.socket_address import SocketAddress
from spinnman.data import SpiNNManDataView
from spinnman.messages.scp.enums.signal import Signal
from pacman.data import PacmanDataView
from pacman.model.graphs.application import ApplicationEdge
# in code to avoid circular import
# from spinn_front_end_common.utility_models import LivePacketGather
# from spinn_front_end_common.utility_models import CommandSender

logger = FormatAdapter(logging.getLogger(__name__))
# pylint: disable=protected-access


class _FecDataModel(object):
    """
    Singleton data model

    This class should not be accessed directly please use the DataView and
    DataWriter classes.
    Accessing or editing the data held here directly is NOT SUPPORTED

    There may be other DataModel classes which sit next to this one and hold
    additional data. The DataView and DataWriter classes will combine these
    as needed.

    What data is held where and how can change without notice.
    """

    __singleton = None

    __slots__ = [
        # Data values cached
        "_buffer_manager",
        "_current_run_timesteps",
        "_data_in_multicast_key_to_chip_map",
        "_data_in_multicast_routing_tables",
        "_database_file_path",
        "_database_socket_addresses",
        "_dsg_targets",
        "_executable_targets",
        "_executable_types",
        "_first_machine_time_step",
        "_fixed_routes",
        "_gatherer_map",
        "_hardware_time_step_ms",
        "_hardware_time_step_us",
        "_ipaddress",
        "_java_caller",
        "_live_packet_recorder_params",
        "_n_boards_required",
        "_n_chips_required",
        "_n_chips_in_graph",
        "_next_sync_signal",
        "_none_labelled_edge_count",
        "_notification_protocol",
        "_max_run_time_steps",
        "_monitor_map",
        "_reset_number",
        "_run_number",
        "_run_step",
        "_simulation_time_step_ms",
        "_simulation_time_step_per_ms",
        "_simulation_time_step_per_s",
        "_simulation_time_step_s",
        "_simulation_time_step_us",
        "_system_multicast_router_timeout_keys",
        "_timestamp_dir_path",
        "_time_scale_factor",
    ]

    def __new__(cls):
        if cls.__singleton:
            return cls.__singleton
        # pylint: disable=protected-access
        obj = object.__new__(cls)
        cls.__singleton = obj
        obj._notification_protocol = None
        obj._clear()
        return obj

    def _clear(self):
        """
        Clears out all data
        """
        # Can not be cleared during hard reset as previous runs data checked
        self._database_socket_addresses = set()
        self._executable_types = None
        self._hardware_time_step_ms = None
        self._hardware_time_step_us = None
        self._live_packet_recorder_params = None
        self._java_caller = None
        self._n_boards_required = None
        self._n_chips_required = None
        self._none_labelled_edge_count = 0
        self._reset_number = 0
        self._run_number = None
        self._simulation_time_step_ms = None
        self._simulation_time_step_per_ms = None
        self._simulation_time_step_per_s = None
        self._simulation_time_step_s = None
        self._simulation_time_step_us = None
        self._time_scale_factor = None
        self._timestamp_dir_path = None
        self._hard_reset()

    def _hard_reset(self):
        """
        Clears out all data that should change after a reset and graaph change
        """
        self._buffer_manager = None
        self._data_in_multicast_key_to_chip_map = None
        self._data_in_multicast_routing_tables = None
        self._database_file_path = None
        self._dsg_targets = None
        self._executable_targets = None
        self._fixed_routes = None
        self._gatherer_map = None
        self._ipaddress = None
        self._n_chips_in_graph = None
        self._next_sync_signal = Signal.SYNC0
        self._notification_protocol = None
        self._max_run_time_steps = None
        self._monitor_map = None
        self._system_multicast_router_timeout_keys = None
        self._soft_reset()
        self._clear_notification_protocol()

    def _soft_reset(self):
        """
        Clears timing and other data that should changed every reset
        """
        self._current_run_timesteps = 0
        self._first_machine_time_step = 0
        self._run_step = None

    def _clear_notification_protocol(self):
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

    See UtilsDataView for a more detailed description.

    This class is designed to only be used directly within none PyNN
    repositories as all methods are available to subclasses
    """

    __fec_data = _FecDataModel()

    __slots__ = []

    # current_run_timesteps and first_machine_time_step

    @classmethod
    def get_current_run_timesteps(cls):
        """
        The end of this or the previous do__run loop time in steps.

        Will be zero if not yet run and not yet in the do_run_loop

        Will be None if in run forever mode

        :rtpye: int or None
        """
        return cls.__fec_data._current_run_timesteps

    @classmethod
    def get_current_run_time_ms(cls):
        """
        The end of this or the previous do__run loop time in ms.

        Semantic sugar for current_run_timesteps * simulation_time_step_ms

        Will be zero if not yet run and not yet in the do_run_loop

        Will be zero if in run forever mode

        :rtpye: float
        """
        if cls.__fec_data._current_run_timesteps is None:
            return 0.0
        return (cls.__fec_data._current_run_timesteps *
                cls.get_simulation_time_step_ms())

    # _buffer_manager
    @classmethod
    def has_buffer_manager(cls):
        """
        Reports if a BufferManager object has already been set

        :return: True if and only if a Buffermanager has been added and not
         reset
        :rtype: bool
        """
        return cls.__fec_data._buffer_manager is not None

    @classmethod
    def get_buffer_manager(cls):
        """
        Returns the buffer manager if known

        :rtype:
            ~spinn_front_end_common.interface.buffer_management.BufferManager
        :raises SpiNNUtilsException:
            If the buffer manager unavailable
        """
        if cls.__fec_data._buffer_manager is None:
            raise cls._exception("buffer_manager")

        return cls.__fec_data._buffer_manager

    @classmethod
    def get_first_machine_time_step(cls):
        """
        The start of this or the next do_run loop time in steps

        Will be None if in run forever mode

        :rtpye: int or None
        """
        return cls.__fec_data._first_machine_time_step

    # max_run_time_steps methods

    @classmethod
    def get_max_run_time_steps(cls):
        """
        Returns the calculated longest time this or a future run loop could be

        Mainly ued to indicate the number of timesteps the vertex can and
        therefore should reserve memry for

        Guaranteed to be positive int if available

        :rtype: int
        :raises SpiNNUtilsException:
            If the max run time is currently unavailable
        """
        if cls.__fec_data._max_run_time_steps is None:
            raise cls._exception("max_run_time_steps")

        return cls.__fec_data._max_run_time_steps

    @classmethod
    def has_max_run_time_steps(cls):
        """
        Indicates if max_run_time_steps is currently available

        :rtype: bool
        """
        return cls.__fec_data._max_run_time_steps is not None

    # simulation_time_step_methods

    @classmethod
    def has_time_step(cls):
        """
        Check if any/all of the time_step values are known

        True When all simulation/hardware_time_step methods are known
        False when none of the simulation/hardware_time_step values are known.
        There is never a case when some are known and others not

        :rtype: bool
        """
        return cls.__fec_data._simulation_time_step_us is not None

    @classmethod
    def get_simulation_time_step_us(cls):
        """ The simulation timestep, in microseconds

        Previously know as "machine_time_step"

        :rtype: int
        :raises SpiNNUtilsException:
            If the simulation_time_step_us is currently unavailable
        """
        if cls.__fec_data._simulation_time_step_us is None:
            raise cls._exception("simulation_time_step_us")
        return cls.__fec_data._simulation_time_step_us

    @classmethod
    def get_simulation_time_step_s(cls):
        """ The simulation timestep, in seconds

        Semantic sugar for simulation_time_step() / 1,000,000.

        :rtype: float
        :raises SpiNNUtilsException:
            If the simulation_time_step_ms is currently unavailable
        """
        if cls.__fec_data._simulation_time_step_us is None:
            raise cls._exception("simulation_time_step_s")
        return cls.__fec_data._simulation_time_step_s

    @classmethod
    def get_simulation_time_step_ms(cls):
        """ The simulation time step, in milliseconds

        Semantic sugar for simulation_time_step_us / 1000.

        :rtype: float
        :raises SpiNNUtilsException:
            If the simulation_time_step_ms is currently unavailable
        """
        if cls.__fec_data._simulation_time_step_us is None:
            raise cls._exception("simulation_time_step_ms")
        return cls.__fec_data._simulation_time_step_ms

    @classmethod
    def get_simulation_time_step_per_ms(cls):
        """ The number of simulation time steps in a millisecond

        Semantic sugar for 1000 / simulation_time_step_us

        :rtype: float
        :raises SpiNNUtilsExceptionn:
            If the simulation_time_step is currently unavailable
        """
        if cls.__fec_data._simulation_time_step_per_ms is None:
            raise cls._exception("simulation_time_step_per_ms")
        return cls.__fec_data._simulation_time_step_per_ms

    @classmethod
    def get_simulation_time_step_per_s(cls):
        """ The number of simulation time steps in a seconds

        Semantic sugar for 1,000,000 / simulation_time_step_us

        :rtype: float
        :raises SpiNNUtilsException:
            If the simulation_time_step is currently unavailable
        """
        if cls.__fec_data._simulation_time_step_per_s is None:
            raise cls._exception("simulation_time_step_per_s")
        return cls.__fec_data._simulation_time_step_per_s

    @classmethod
    def get_hardware_time_step_ms(cls):
        """ The hardware timestep, in milliseconds

        Semantic sugar for simulation_time_step_ms * time_scale_factor

        :rtype: float
        :raises SpiNNUtilsException:
            If the hardware_time_step is currently unavailable
        """
        if cls.__fec_data._hardware_time_step_ms is None:
            raise cls._exception("hardware_time_step_ms")
        return cls.__fec_data._hardware_time_step_ms

    @classmethod
    def get_hardware_time_step_us(cls):
        """ The hardware timestep, in microseconds

        Semantic sugar for simulation_time_step_us * time_scale_factor

        :rtype: int
        :raises SpiNNUtilsException:
            If the hardware_time_step is currently unavailable
        """
        if cls.__fec_data._hardware_time_step_us is None:
            raise cls._exception("ardware_time_step_us")
        return cls.__fec_data._hardware_time_step_us

    # time scale factor

    @classmethod
    def get_time_scale_factor(cls):
        """

        :rtype: int or float
        :raises SpiNNUtilsException:
            If the time_scale_factor is currently unavailable
        :raises SpiNNUtilsException:
            If the time_scale_factor is currently unavailable
        """
        if cls.__fec_data._time_scale_factor is None:
            raise cls._exception("time_scale_factor")
        return cls.__fec_data._time_scale_factor

    @classmethod
    def has_time_scale_factor(cls):
        """

        :rtype: bool
        """
        return cls.__fec_data._time_scale_factor is not None

    #  reset number

    @classmethod
    def get_reset_number(cls):
        """
        Get the number of times a reset has happened.

        Only counts the first reset after each run.

        So resets that are first soft then hard are ignored.
        Double reset calls without a run and resets before run are ignored.

        Reset numbers start at zero

        :return:
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the run_number is currently unavailable
        """
        if cls.__fec_data._reset_number is None:
            raise cls._exception("run_number")
        return cls.__fec_data._reset_number

    @classmethod
    def get_reset_str(cls):
        """
        Get the number of times a reset has happene as a string. Zero as ""

        Only counts the first reset after each run.

        So resets that are first soft then hard are ignored.
        Double reset calls without a run and resets before run are ignored.

        Reset numbers start at zero

        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the run_number is currently unavailable
        """
        if cls.__fec_data._reset_number is None:
            raise cls._exception("run_number")
        if cls.__fec_data._reset_number:
            return str(cls.__fec_data._reset_number)
        else:
            return ""

    #  run number

    @classmethod
    def get_run_number(cls):
        """
        Get the number of this or the next run.

        Run numbers start at 1

        :return:
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the run_number is currently unavailable
        """
        if cls.__fec_data._run_number is None:
            raise cls._exception("run_number")
        return cls.__fec_data._run_number

    @classmethod
    def get_run_step(cls):
        """
        Get the auto pause and resume step currently running if any.

        If and only if currently in an auto pause and resume loop this will
        report the number of the step. Starting at 1

        In most cases this will return None, including when running without
        steps.

        :rtype: None or int
        """
        return cls.__fec_data._run_step

    # Report directories
    # There are NO has or get methods for directories
    # This allows directories to be created on the fly

    # n_boards/chips required

    @classmethod
    def has_n_boards_required(cls):
        """
        Reports if a user has sets the number of boards requested during setup

        :rtype: bool
        :raises SpiNNUtilsException:
            If n_boards_required is not set or set to None
        """
        return cls.__fec_data._n_boards_required is not None

    @classmethod
    def get_n_boards_required(cls):
        """
        Gets the number of boards requested by the user during setup if known.

        Guaranteed to be positive

        :rtype: int
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the n_boards_required is currently unavailable
        """
        if cls.__fec_data._n_boards_required is None:
            raise cls._exception("n_boards_requiredr")
        return cls.__fec_data._n_boards_required

    @classmethod
    def get_n_chips_needed(cls):
        """
        Gets the number of chips needed if set

        This will be the number of chips requested by the user during setup,
        even if this is less that what the partitioner reported.

        If the partitioner has run and the user has not specified a number,
        this will be what the partitioner requested.

        Guaranteed to be positive if set

        :rtype: int
        :raises SpiNNUtilsException:
            If data for n_chips_needed is not available
        """
        if cls.__fec_data._n_chips_required:
            return cls.__fec_data._n_chips_required
        if cls.__fec_data._n_chips_in_graph:
            return cls.__fec_data._n_chips_in_graph
        raise cls._exception("n_chips_requiredr")

    @classmethod
    def has_n_chips_needed(cls):
        """
        Detects if the number of chips needed has been set.

        This will be the number of chips requested by the use during setup or
        what the partitioner requested.

        :rtype: bool
        """
        if cls.__fec_data._n_chips_required is not None:
            return True
        return cls.__fec_data._n_chips_in_graph is not None

    @classmethod
    def get_timestamp_dir_path(cls):
        """
        Returns path to existing timestamped director in the reports directory

        ..note: In unittest mode this returns a tempdir
        shared by all path methods

        :rtpye: str
        :raises SpiNNUtilsException:
            If the simulation_time_step is currently unavailable
        """
        if cls.__fec_data._timestamp_dir_path:
            return cls.__fec_data._timestamp_dir_path
        if cls._is_mocked():
            return cls._temporary_dir_path()
        raise cls._exception("timestamp_dir_path")

    # system multicast routing data

    @classmethod
    def get_data_in_multicast_key_to_chip_map(cls):
        """
        Retreive the data_in_multicast_key_to_chip_map if known

        :rtype: dict
        :raises SpiNNUtilsException:
            If the data_in_multicast_key_to_chip_map is currently unavailable
        """
        if cls.__fec_data._data_in_multicast_key_to_chip_map is None:
            raise cls._exception("data_in_multicast_key_to_chip_map")
        return cls.__fec_data._data_in_multicast_key_to_chip_map

    @classmethod
    def get_data_in_multicast_routing_tables(cls):
        """
        Retreive the data_in_multicast_routing_tables if known

        :rtype: MulticastRoutingTables
        :raises SpiNNUtilsException:
            If the data_in_multicast_routing_tables is currently unavailable
        """
        if cls.__fec_data._data_in_multicast_routing_tables is None:
            raise cls._exception("data_in_multicast_routing_tables")
        return cls.__fec_data._data_in_multicast_routing_tables

    @classmethod
    def get_system_multicast_router_timeout_keys(cls):
        """
        Retreive the system_multicast_router_timeout_keys if known

        :rtype: dict
        :raises SpiNNUtilsException:
            If the system_multicast_router_timeout_keys is currently
            unavailable
        """
        if cls.__fec_data._system_multicast_router_timeout_keys is None:
            raise cls._exception("system_multicast_router_timeout_keys")
        return cls.__fec_data._system_multicast_router_timeout_keys

    # ipaddress

    @classmethod
    def has_ipaddress(cls):
        """
        Detects if the ipaddress of the board with chip 0,0 if known

        :return:
        """
        return cls.__fec_data._ipaddress is not None

    @classmethod
    def get_ipaddress(cls):
        """
        Gets the ipaddress of the board with chip 0,0 if it has been set

        :rtype: str
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the ipaddress is currently unavailable
        """
        if cls.__fec_data._ipaddress is None:
            if cls._is_mocked():
                return "127.0.0.1"
            raise cls._exception("ipaddress")
        return cls.__fec_data._ipaddress

    # fixed_routes
    @classmethod
    def get_fixed_routes(cls):
        """
        Gets the fixed routes if they have been created

        :rtype: dict(tuple(int,int), ~spinn_machine.FixedRouteEntry)
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the fixed_routes is currently unavailable
        """
        if cls.__fec_data._fixed_routes is None:
            raise cls._exception("fixed_routes")
        return cls.__fec_data._fixed_routes

    @classmethod
    def has_java_caller(cls):
        """
        Reports if there is a Java called that can be used.

        Equivellent to get_config_bool("Java", "use_java") as the writer will
        have created the caller during setup

        The behaviour when Mocked is currently to always return False.

        :rtype: bool
        """
        return cls.__fec_data._java_caller is not None

    @classmethod
    def get_java_caller(cls):
        """
        Gets the Java_caller

        :rtype: str
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the java_caller is currently unavailable
        """
        if cls.__fec_data._java_caller is None:
            raise cls._exception("java_caller")
        return cls.__fec_data._java_caller

    # run_dir_path in UtilsDataView

    @classmethod
    def get_json_dir_path(cls):
        """
        Returns the path to the directory that holds all json files

        This will be the path used by the last run call or to be used by
        the next run if it has not yet been called.

        ..note: In unittest mode this returns a tempdir
        shared by all path methods

        :rtpye: str
        :raises SpiNNUtilsException:
            If the simulation_time_step is currently unavailable
        """
        if cls._is_mocked():
            return cls._temporary_dir_path()

        return cls._child_folder(cls.get_run_dir_path(), "json_files")

    @classmethod
    def get_provenance_dir_path(cls):
        """
        Returns the path to the directory that holds all provenance files

        This will be the path used by the last run call or to be used by
        the next run if it has not yet been called.

        ..note: In unittest mode this returns a tempdir
        shared by all path methods

        :rtpye: str
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the simulation_time_step is currently unavailable
        """
        if cls._is_mocked():
            return cls._temporary_dir_path()
        return cls._child_folder(cls.get_run_dir_path(), "provenance_data")

    @classmethod
    def get_app_provenance_dir_path(cls):
        """
        Returns the path to the directory that holds all app provenance files

        This will be the path used by the last run call or to be used by
        the next run if it has not yet been called.

        ..note: In unittest mode this returns a tempdir
        shared by all path methods

        :rtpye: str
        :raises ~spinn_utilities.exceptions.SimulatorNotSetupException:
            If the simulator has not been setup
        """
        if cls._is_mocked():
            return cls._temporary_dir_path()

        return cls._child_folder(
            cls.get_provenance_dir_path(), "app_provenance_data")

    @classmethod
    def get_system_provenance_dir_path(cls):
        """
        Returns the path to the directory that holds all provenance files

        This will be the path used by the last run call or to be used by
        the next run if it has not yet been called.

        ..note: In unittest mode this returns a tempdir
        shared by all path methods

        :rtpye: str
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the simulation_time_step is currently unavailable
        """
        if cls._is_mocked():
            return cls._temporary_dir_path()
        return cls._child_folder(
            cls.get_provenance_dir_path(), "system_provenance_data")

    @classmethod
    def _child_folder(cls, parent, child_name, must_create=False):
        """
        :param str parent:
        :param str child_name:
        :param bool must_create:
            If `True`, the directory named by `child_name` (but not necessarily
            its parents) must be created by this call, and an exception will be
            thrown if this fails.
        :return: The fully qualified name of the child folder.
        :rtype: str
        :raises OSError: if the directory existed ahead of time and creation
            was required by the user
        """
        child = os.path.join(parent, child_name)
        if must_create:
            # Throws OSError or FileExistsError (a subclass of OSError) if the
            # directory exists.
            os.makedirs(child)
        elif not os.path.exists(child):
            os.makedirs(child, exist_ok=True)
        return child

    @classmethod
    def get_next_none_labelled_edge_number(cls):
        """
        Returns an unused number for a none_labelled_edge

        :rtpye int:
        """
        cls.__fec_data._none_labelled_edge_count += 1
        return cls.__fec_data._none_labelled_edge_count

    @classmethod
    def get_next_sync_signal(cls):
        """
        Returns alteratively Signal.SYNC0 and Signal.SYNC1

        :rtpye  ~spinnman.messages.scp.enums.signal.Signal:
        """
        if cls.__fec_data._next_sync_signal == Signal.SYNC0:
            cls.__fec_data._next_sync_signal = Signal.SYNC1
            return Signal.SYNC0
        else:
            cls.__fec_data._next_sync_signal = Signal.SYNC0
            return Signal.SYNC1

    @classmethod
    def get_executable_types(cls):
        """
        Gets the _executable_types if they have been created

        :rtype: dict(
            ~spinn_front_end_common.utilities.utility_objs.ExecutableType,
            ~spinn_machine.CoreSubsets)
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the executable_types is currently unavailable
        """
        if cls.__fec_data._executable_types is None:
            raise cls._exception("executable_types")
        return cls.__fec_data._executable_types

    @classmethod
    def has_live_packet_recorder_params(cls):
        """
        Reports if there are live_packet_recorder_params

        If True the live_packet_recorder_params not be empty

        :rtype bool
        """
        return cls.__fec_data._live_packet_recorder_params is not None

    @classmethod
    def get_live_packet_recorder_params(cls):
        """
        Mapping of live_packet_gatherer_params to a list of tuples\
        (vertex and list of ids))

        :rtype: dict(live_packet_gatherer_params, (vertex, list(str))
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the _live_packet_recorder_params is currently unavailable
        """
        if cls.__fec_data._live_packet_recorder_params is None:
            raise cls._exception("live_packet_recorder_params")
        return cls.__fec_data._live_packet_recorder_params

    # Add method in view so add can be done without going through ASB
    @classmethod
    def add_live_packet_gatherer_parameters(
            cls, live_packet_gatherer_params, vertex_to_record_from,
            partition_ids):
        """ Adds parameters for a new LPG if needed, or adds to the tracker \
            for parameters.

            Note If the Application Graph is used the vertex must be an
            Application Vertex if not it must be a MachineVertex

        :param LivePacketGatherParameters live_packet_gatherer_params:
            params to look for a LPG
        :param ~pacman.model.graphs.AbstractVertex vertex_to_record_from:
            the vertex that needs to send to a given LPG
        :param iterable(str) partition_ids:
            the IDs of the partitions to connect from the vertex
        """
        if cls.__fec_data._live_packet_recorder_params is None:
            # pylint: disable=attribute-defined-outside-init
            cls.__fec_data._live_packet_recorder_params = dict()
        lpg_vertex = cls.__fec_data._live_packet_recorder_params.get(
            live_packet_gatherer_params)
        if lpg_vertex is None:
            # UGLY import due to circular reference
            from spinn_front_end_common.utility_models import LivePacketGather
            lpg_vertex = LivePacketGather(
                live_packet_gatherer_params, live_packet_gatherer_params.label)
            cls.__fec_data._live_packet_recorder_params[
                live_packet_gatherer_params] = lpg_vertex
            cls.add_vertex(lpg_vertex)
        for part_id in partition_ids:
            cls.add_edge(
                ApplicationEdge(vertex_to_record_from, lpg_vertex), part_id)

    @classmethod
    def get_database_file_path(cls):
        """
        Will return the database_file_path if set or None if not set
        or set to None

        :rtype: str or None
        """
        return cls.__fec_data._database_file_path

    @classmethod
    def get_executable_targets(cls):
        """
        binaries to be executed.

        :rtype: ExecutableTargets
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the executable_targets is currently unavailable
        """
        if cls.__fec_data._executable_targets is None:
            raise cls._exception("executable_targets")
        return cls.__fec_data._executable_targets

    @classmethod
    def get_dsg_targets(cls):
        """ data Spec targets database

        :rtype: DsSqlliteDatabase
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the dsg_targets is currently unavailable
        """
        if cls.__fec_data._dsg_targets is None:
            raise cls._exception("dsg_targets")
        return cls.__fec_data._dsg_targets

    @classmethod
    def has_monitors(cls):
        """
        Detect is ExtraMonitorSupportMachineVertex(s) have been created

        :rtype: bool
        """
        return cls.__fec_data._monitor_map is not None

    @classmethod
    def get_monitor_by_xy(cls, x, y):
        """ ExtraMonitorSupportMachineVertex for core x, y

        :rtype: ExtraMonitorSupportMachineVertex
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the monitors are currently unavailable
        :raises KeyError: If core x,y does not have a monitor
        """
        if cls.__fec_data._monitor_map is None:
            raise cls._exception("monitors_map")
        # pylint: disable=unsubscriptable-object
        return cls.__fec_data._monitor_map[(x, y)]

    @classmethod
    def iterate_monitor_items(cls):
        """
        Iterates over the (X,y) and ExtraMonitorSupportMachineVertex

        get_n_monitors returns the number of items this iterable will provide

        :rtype: iterable(tuple(tuple(int,int),
            ExtraMonitorSupportMachineVertex))
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the monitors are currently unavailable
        """
        if cls.__fec_data._monitor_map is None:
            raise cls._exception("monitors_map")
        return cls.__fec_data._monitor_map.items()

    @classmethod
    def get_n_monitors(cls):
        """
        Number of ExtraMonitorSupportMachineVertexs

        :rtype: int
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the monitors are currently unavailable
        """
        if cls.__fec_data._monitor_map is None:
            raise cls._exception("monitors_map")
        return len(cls.__fec_data._monitor_map)

    @classmethod
    def iterate_monitors(cls):
        """
        Iterates over the ExtraMonitorSupportMachineVertex(s)

        :rtype: iterable(ExtraMonitorSupportMachineVertex)
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the monitors are currently unavailable
        """
        if cls.__fec_data._monitor_map is None:
            raise cls._exception("monitors_map")
        return cls.__fec_data._monitor_map.values()

    @classmethod
    def get_gatherer_by_xy(cls, x, y):
        """ DataSpeedUpPacketGatherMachineVertex for core x, y

        :rtype: DataSpeedUpPacketGatherMachineVertex
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the gatherers are currently unavailable
        :raises KeyError: If core x,y does not have a monitor
        """
        if cls.__fec_data._gatherer_map is None:
            raise cls._exception("gatherer_map")
        # pylint: disable=unsubscriptable-object
        return cls.__fec_data._gatherer_map[(x, y)]

    @classmethod
    def iterate_gather_items(cls):
        """
        Iterates over the (X,y) and  DataSpeedUpPacketGatherMachineVertex

        get_n_gathers returns the number of items this iterable will provide

        :rtype: iterable(tuple(tuple(int,int),
             DataSpeedUpPacketGatherMachineVertex))
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the gathers are currently unavailable
        """
        if cls.__fec_data._gatherer_map is None:
            raise cls._exception("gatherer_map")
        return cls.__fec_data._gatherer_map.items()

    @classmethod
    def get_n_gathers(cls):
        """
        Number of DataSpeedUpPacketGatherMachineVertex(s)

        :rtype: int
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the gathers are currently unavailable
        """
        if cls.__fec_data._gatherer_map is None:
            raise cls._exception("gatherer_map")
        return len(cls.__fec_data._gatherer_map)

    @classmethod
    def iterate_gathers(cls):
        """
        Iterates over the DataSpeedUpPacketGatherMachineVertex(s)

        :rtype: iterable(DataSpeedUpPacketGatherMachineVertex)
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the gathers are currently unavailable
        """
        if cls.__fec_data._gatherer_map is None:
            raise cls._exception("gatherer_map")
        return cls.__fec_data._gatherer_map.values()

    @classmethod
    def iterate_database_socket_addresses(cls):
        """
        Iterates over the registered database_socket_addresses

        :rtype: iterable(~spinn_utilities.socket_address.SocketAddress)
        """
        return iter(cls.__fec_data._database_socket_addresses)

    @classmethod
    def get_n_database_socket_addresses(cls):
        """
        Number of registered database_socket_addresses

        :rtype: int
        """
        return len(cls.__fec_data._database_socket_addresses)

    @classmethod
    def add_database_socket_address(cls, database_socket_address):
        """
        Adds a socket address to the list of known addresses

        :param SocketAddress database_socket_address:
        :raises TypeError: if database_socket_address is not a SocketAddress
        """
        if not isinstance(database_socket_address, SocketAddress):
            raise TypeError("database_socket_address must be a SocketAddress")
        cls.__fec_data._database_socket_addresses.add(database_socket_address)

    @classmethod
    def add_database_socket_addresses(cls, database_socket_addresses):
        """
        Adds all socket addresses to the list of known addresses

        :param iterable(SocketAddress) database_socket_addresses:
        :raises TypeError:
           if database_socket_address is not a iterable(SocketAddress)
        """
        if database_socket_addresses is None:
            return
        for socket_address in database_socket_addresses:
            cls.add_database_socket_address(socket_address)

    @classmethod
    def get_notification_protocol(cls):
        """
        binaries to be executed.

        :rtype: NotificationProtocol
        :raises ~spinn_utilities.exceptions.SpiNNUtilsException:
            If the notification_protocol is currently unavailable
        """
        if cls.__fec_data._notification_protocol is None:
            raise cls._exception("notification_protocol")
        return cls.__fec_data._notification_protocol
