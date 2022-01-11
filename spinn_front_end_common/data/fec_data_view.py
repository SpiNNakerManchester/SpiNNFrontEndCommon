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
from pacman.data import PacmanDataView


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
        "_current_run_timesteps",
        "_first_machine_time_step",
        "_hardware_time_step_ms",
        "_hardware_time_step_us",
        "_n_calls_to_run",
        "_max_run_time_steps",
        "_report_dir_path",
        "_simulation_time_step_ms",
        "_simulation_time_step_per_ms",
        "_simulation_time_step_per_s",
        "_simulation_time_step_s",
        "_simulation_time_step_us",
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
        self._hardware_time_step_ms = None
        self._hardware_time_step_us = None
        self._n_calls_to_run = None
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
        self._max_run_time_steps = None
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
    def get_n_calls_to_run(self):
        """
        The number of this or the next call to run or None if not Known

        :rtpye: int
        """
        try:
            if self.get_status() == Data_Status.IN_RUN:
                return self.__fec_data._n_calls_to_run
            else:
                # This is the current behaviour in ASB
                return self.__fec_data._n_calls_to_run + 1
        except TypeError:
            return None

    @property
    def n_calls_to_run(self):
        """
        The number of this or the next call to run

        :rtpye: int
        """
        if self.__fec_data._n_calls_to_run is None:
            raise self._exception("n_calls_to_run")
        if self.get_status() == Data_Status.IN_RUN:
            return self.__fec_data._n_calls_to_run
        else:
            # This is the current behaviour in ASB
            return self.__fec_data._n_calls_to_run + 1

    def has_n_calls_to_run(self):
        return self.__fec_data._n_calls_to_run is not None

    # Report directories
    # There are NO has or get methods for directories
    # This allow directories to be created on the fly

    @property
    def report_dir_path(self):
        """
        Returns path to existing reports directory

        ..note: In unittest mode this returns a tempdir
        shared by all path methods

        :rtpye: str
        :raises SpiNNUtilsException:
            If the simulation_time_step is currently unavailable
        """
        if self.__fec_data._report_dir_path:
            return self.__fec_data._report_dir_path
        if self.get_status() == Data_Status.MOCKED:
            return self._temporary_dir_path()
        raise self._exception("report_dir_path")

    @property
    def timestamp_dir_path(self):
        """
        Returns path to existing timestamped director in the reports directory

        ..note: In unittest mode this returns a tempdir
        shared by all path methods

        :rtpye: str
        :raises SpiNNUtilsException:
            If the simulation_time_step is currently unavailable
        """
        if self.__fec_data._timestamp_dir_path:
            return self.__fec_data._timestamp_dir_path
        if self.get_status() == Data_Status.MOCKED:
            return self._temporary_dir_path()
        raise self._exception("timestamp_dir_path")

    # run_dir_path in UtilsDataView

    @property
    def json_dir_path(self):
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
        if self.get_status() == Data_Status.MOCKED:
            return self._temporary_dir_path()

        return self._child_folder(self.get_run_dir_path(), "json_files")

    @property
    def provenance_dir_path(self):
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
        if self.get_status() == Data_Status.MOCKED:
            return self._temporary_dir_path()
        return self._child_folder(self.get_run_dir_path(), "provenance_data")

    @property
    def app_provenance_dir_path(self):
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
        if self.get_status() == Data_Status.MOCKED:
            return self._temporary_dir_path()

        return self._child_folder(
            self.provenance_dir_path, "app_provenance_data")

    @property
    def system_provenance_dir_path(self):
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
        if self.get_status() == Data_Status.MOCKED:
            return self._temporary_dir_path()
        return self._child_folder(
            self.provenance_dir_path, "system_provenance_data")

    def _child_folder(self, parent, child_name, must_create=False):
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
            self._make_dirs(child)
        return child

    @staticmethod
    def _make_dirs(path):
        # Workaround for Python 2/3 Compatibility (Python 3 raises on exists)
        try:
            os.makedirs(path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
