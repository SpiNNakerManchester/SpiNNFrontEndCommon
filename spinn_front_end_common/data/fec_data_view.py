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

import errno
import os
from spinn_utilities.data.data_status import Data_Status
from spinnman.data import SpiNNManDataView
from spinnman.messages.scp.enums.signal import Signal
from pacman.data import PacmanDataView
from pacman.model.graphs.application import ApplicationVertex
from pacman.model.graphs.machine import MachineVertex
from spinn_front_end_common.utilities.utility_objs import (
    LivePacketGatherParameters)
from spinn_front_end_common.utilities.exceptions import ConfigurationException


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
        "_app_id",
        "_buffer_manager",
        "_current_run_timesteps",
        "_data_in_multicast_key_to_chip_map",
        "_data_in_multicast_routing_tables",
        "_executable_types",
        "_first_machine_time_step",
        "_fixed_routes",
        "_hardware_time_step_ms",
        "_hardware_time_step_us",
        "_ipaddress",
        "_java_caller",
        "_live_packet_recorder_params",
        "_n_boards_required",
        "_n_calls_to_run",
        "_n_chips_required",
        "_n_chips_in_graph",
        "_next_sync_signal",
        "_none_labelled_edge_count",
        "_max_run_time_steps",
        "_report_dir_path",
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
        obj._clear()
        return obj

    def _clear(self):
        """
        Clears out all data
        """
        # Can not be cleared during hard reset as previous runs data checked
        self._executable_types = None
        self._hardware_time_step_ms = None
        self._hardware_time_step_us = None
        self._live_packet_recorder_params = None
        self._java_caller = None
        self._n_boards_required = None
        self._n_calls_to_run = None
        self._n_chips_required = None
        self._none_labelled_edge_count = 0
        self._simulation_time_step_ms = None
        self._simulation_time_step_per_ms = None
        self._simulation_time_step_per_s = None
        self._simulation_time_step_s = None
        self._simulation_time_step_us = None
        self._report_dir_path = None
        self._time_scale_factor = None
        self._timestamp_dir_path = None
        self._hard_reset()

    def _hard_reset(self):
        """
        Clears out all data that should change after a reset and graaph change
        """
        self._app_id = None
        self._buffer_manager = None
        self._data_in_multicast_key_to_chip_map = None
        self._data_in_multicast_routing_tables = None
        self._fixed_routes = None
        self._ipaddress = None
        self._n_chips_in_graph = None
        self._next_sync_signal = Signal.SYNC0
        self._max_run_time_steps = None
        self._system_multicast_router_timeout_keys = None
        self._soft_reset()

    def _soft_reset(self):
        """
        Clears timing and other data that should changed every reset
        """
        self._current_run_timesteps = 0
        self._first_machine_time_step = 0


class FecDataView(PacmanDataView, SpiNNManDataView):
    """
    A read only view of the data available at FEC level

    The objects accessed this way should not be changed or added to.
    Changing or adding to any object accessed if unsupported as bypasses any
    check or updates done in the writer(s).
    Objects returned could be changed to immutable versions without notice!

    The get methods will return either the value if known or a None.
    This is the faster way to access the data but lacks the safety.

    The property methods will either return a valid value or
    raise an Exception if the data is currently not available.
    These are typically semantic sugar around the get methods.

    The has methods will return True is the value is known and False if not.
    Semantically the are the same as checking if the get returns a None.
    They may be faster if the object needs to be generated on the fly or
    protected to be made immutable.

    While how and where the underpinning DataModel(s) store data can change
    without notice, methods in this class can be considered a supported API
    """

    __fec_data = _FecDataModel()

    __slots__ = []

    # app_id methods

    @classmethod
    def get_app_id(cls):
        if cls.__fec_data._app_id is None:
            cls.__fec_data._app_id = cls.get_new_id()
        return cls.__fec_data._app_id

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
        therefor should reserve memry for

        Guranteed to be possitve

        :rtype: None or int
        :raises SpiNNUtilsException:
            If the max run time is currently unavailable
        """
        if cls.__fec_data._max_run_time_steps is None:
            raise cls._exception("max_run_time_steps")

        return cls.__fec_data._max_run_time_steps

    @classmethod
    def has_max_run_time_steps(cls):
        return cls.__fec_data._max_run_time_steps is not None

    # simulation_time_step_methods

    @classmethod
    def has_time_step(cls):
        """
        Check if any/all of the time_step values are known

        True When all simulation_time_step are known
        False when none of the simulation_time_step values are known.
        There is never a case when some are known and others not

        :rtype: bool
        """
        return cls.__fec_data._simulation_time_step_us is not None

    @classmethod
    def get_simulation_time_step_us(cls):
        """ The simulation timestep, in microseconds or None if not known

        Previously know as "machine_time_step"

        :rtype: int or None
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
        """ The simulation time step, in milliseconds or None if not known

        Semantic sugar for simulation_time_step_us / 1000.

        :rtype: float or None
        """
        if cls.__fec_data._simulation_time_step_us is None:
            raise cls._exception("simulation_time_step_ms")
        return cls.__fec_data._simulation_time_step_ms

    @classmethod
    def get_simulation_time_step_per_ms(cls):
        """ The simulation time step in a milliseconds or None if not known

        Semantic sugar for 1000 / simulation_time_step_us

        :rtype: float or None
        :raises SpiNNUtilsExceptionn:
            If the simulation_time_step is currently unavailable
        """
        if cls.__fec_data._simulation_time_step_per_ms is None:
            raise cls._exception("simulation_time_step_per_ms")
        return cls.__fec_data._simulation_time_step_per_ms

    @classmethod
    def get_simulation_time_step_per_s(cls):
        """ The simulation time step in a seconds or None if not known

        Semantic sugar for 1,000,000 / simulation_time_step_us

        :rtype: float or None
        :raises SpiNNUtilsException:
            If the simulation_time_step is currently unavailable
        """
        if cls.__fec_data._simulation_time_step_per_s is None:
            raise cls._exception("simulation_time_step_per_s")
        return cls.__fec_data._simulation_time_step_per_s

    @classmethod
    def get_hardware_time_step_ms(cls):
        """ The hardware timestep, in milliseconds or None if not known

        Semantic sugar for simulation_time_step_ms * time_scale_factor

        :rtype: float or None
        """
        if cls.__fec_data._hardware_time_step_ms is None:
            raise cls._exception("hardware_time_step_ms")
        return cls.__fec_data._hardware_time_step_ms

    @classmethod
    def get_hardware_time_step_us(cls):
        """ The hardware timestep, in microeconds or None if not known

        Semantic sugar for simulation_time_step_us * time_scale_factor

        :rtype: int or None
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

    # n calls_to run

    # The data the user gets needs not be the exact data cached
    @classmethod
    def get_n_calls_to_run(cls):
        """
        The number of this or the next call to run or None if not Known

        :rtpye: int
        """
        if cls.__fec_data._n_calls_to_run is None:
            raise cls._exception("n_calls_to_run")
        if cls.get_status() == Data_Status.IN_RUN:
            return cls.__fec_data._n_calls_to_run
        else:
            # This is the current behaviour in ASB
            return cls.__fec_data._n_calls_to_run + 1

    @classmethod
    def has_n_calls_to_run(cls):
        return cls.__fec_data._n_calls_to_run is not None

    # Report directories
    # There are NO has or get methods for directories
    # This allow directories to be created on the fly

    # n_boards/chips required

    @classmethod
    def has_n_boards_required(cls):
        """
        Reports is a user has sets the number of boards requested during setup

        :rtype: bool
        :raises SpiNNUtilsException:
            If n_boards_required is not set or set to None
        """
        return cls.__fec_data._n_boards_required is not None

    @classmethod
    def get_n_boards_required(cls):
        """
        Gets the number of boards requested by the user during setup is known.

        Guaranteed to be positive

        :rtype: int
        """
        if cls.__fec_data._n_boards_required is None:
            raise cls._exception("n_boards_requiredr")
        return cls.__fec_data._n_boards_required

    @classmethod
    def get_n_chips_needed(cls):
        """
        Gets the number of chips needed if set

        This will be the number of chips requested by the use during setup,
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
    def get_report_dir_path(cls):
        """
        Returns path to existing reports directory

        ..note: In unittest mode this returns a tempdir
        shared by all path methods

        :rtpye: str
        :raises SpiNNUtilsException:
            If the simulation_time_step is currently unavailable
        """
        if cls.__fec_data._report_dir_path:
            return cls.__fec_data._report_dir_path
        if cls.get_status() == Data_Status.MOCKED:
            return cls._temporary_dir_path()
        raise cls._exception("report_dir_path")

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
        if cls.get_status() == Data_Status.MOCKED:
            return cls._temporary_dir_path()
        raise cls._exception("timestamp_dir_path")

    # system multicast routing data

    @classmethod
    def get_data_in_multicast_key_to_chip_map(cls):
        if cls.__fec_data._data_in_multicast_key_to_chip_map is None:
            raise cls._exception("data_in_multicast_key_to_chip_map")
        return cls.__fec_data._data_in_multicast_key_to_chip_map

    @classmethod
    def get_data_in_multicast_routing_tables(cls):
        if cls.__fec_data._data_in_multicast_routing_tables is None:
            raise cls._exception("data_in_multicast_routing_tables")
        return cls.__fec_data._data_in_multicast_routing_tables

    @classmethod
    def get_system_multicast_router_timeout_keys(cls):
        if cls.__fec_data._system_multicast_router_timeout_keys is None:
            raise cls._exception("system_multicast_router_timeout_keys")
        return cls.__fec_data._system_multicast_router_timeout_keys

    # ipaddress

    @classmethod
    def has_ipaddress(cls):
        return cls.__fec_data._ipaddress is not None

    @classmethod
    def get_ipaddress(cls):
        """
        Gets the ipaddress or the board with chip 0,0 if it has been set

        :rtype: str
        """
        if cls.__fec_data._ipaddress is None:
            raise cls._exception("ipaddress")
        return cls.__fec_data._ipaddress

    # fixed_routes
    @classmethod
    def get_fixed_routes(cls):
        """
        Gets the fixed routes if they have been created

        :rtype: dict(tuple(int,int), ~spinn_machine.FixedRouteEntry)
        """
        if cls.__fec_data._fixed_routes is None:
            raise cls._exception("fixed_routes")
        return cls.__fec_data._fixed_routes

    @classmethod
    def has_java_caller(cls):
        """
        Reports if there is a Java called that can be used.

        Equivellent to get_config_bool("Java", "use_java") as the writer will
        have created the caller durring setup

        The behaviour when Mocked is currently to always return False.

        :rtype: bool
        """
        return cls.__fec_data._java_caller is not None

    @classmethod
    def get_java_caller(cls):
        """
        Gets the Java_caller

        :rtype: str
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
        if cls.get_status() == Data_Status.MOCKED:
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
        if cls.get_status() == Data_Status.MOCKED:
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
        if cls.get_status() == Data_Status.MOCKED:
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
        if cls.get_status() == Data_Status.MOCKED:
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
            cls._make_dirs(child)
        return child

    @staticmethod
    def _make_dirs(path):
        # Workaround for Python 2/3 Compatibility (Python 3 raises on exists)
        try:
            os.makedirs(path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

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
            ~spinn_machine.CoreSubsets or None)
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
        :param list(str) partition_ids:
            the IDs of the partitions to connect from the vertex
        """
        if cls.get_graph().n_vertices > 0:
            if not isinstance(vertex_to_record_from, ApplicationVertex):
                raise ConfigurationException(
                    "vertex_to_record_from must be an ApplicationVertex when "
                    "Application level used")
        elif cls.get_machine_graph().n_vertices > 0:
            if not isinstance(vertex_to_record_from, MachineVertex):
                raise ConfigurationException(
                    "vertex_to_record_from must be an MachineVertex when"
                    "only Machine Level used")
        else:
            raise ConfigurationException(
                "Please add vertices to the Graph before calling this method")

        if not isinstance(
                live_packet_gatherer_params, LivePacketGatherParameters):
            raise ConfigurationException(
                "live_packet_gatherer_params must be a "
                "LivePacketGatherParameters")

        if not isinstance(partition_ids, list):
            raise ConfigurationException(
                "partition_ids must be a list of str")

        if cls.__fec_data._live_packet_recorder_params is None:
            cls.__fec_data._live_packet_recorder_params = dict()
        if live_packet_gatherer_params in \
                cls.__fec_data._live_packet_recorder_params:
            cls.__fec_data._live_packet_recorder_params[
                live_packet_gatherer_params].append(
                (vertex_to_record_from, partition_ids))
        else:
            cls.__fec_data._live_packet_recorder_params[
                live_packet_gatherer_params] = [
                (vertex_to_record_from, partition_ids)]
