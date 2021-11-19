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

from .data_status import Data_Status


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
        "_hardware_time_step_ms",
        "_hardware_time_step_us",
        "_provenance_file_path",
        "_simulation_time_step_ms",
        "_simulation_time_step_per_ms",
        "_simulation_time_step_per_s",
        "_simulation_time_step_s",
        "_simulation_time_step_us",
        "_n_calls_to_run",
        "_report_default_directory",
        "_time_scale_factor",
        # Data status mainly to raise best Exception
        "_status"
    ]

    def __new__(cls):
        if cls.__singleton:
            return cls.__singleton
        # pylint: disable=protected-access
        obj = object.__new__(cls)
        cls.__singleton = obj
        obj._clear()
        obj._status = Data_Status.NOT_SETUP
        return obj

    def _clear(self):
        """
        Clears out all data
        """
        self._app_id = None
        self._hardware_time_step_ms = None
        self._hardware_time_step_us = None
        self._provenance_file_path = None
        self._simulation_time_step_ms = None
        self._simulation_time_step_per_ms = None
        self._simulation_time_step_per_s = None
        self._simulation_time_step_s = None
        self._simulation_time_step_us = None
        self._n_calls_to_run = None
        self._report_default_directory = None
        self._time_scale_factor = None


class FecDataView(object):
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

    def exception(self, data):
        return self.__fec_data._status.exception(data)

    # app_id methods

    def get_app_id(self):
        """
        The current application id or None if not known

        :rtype: int or None
        """
        return self.__fec_data._app_id

    @property
    def app_id(self):
        """
        The current application id

        :rtype: int
        :raises SpinnFrontEndException:
            If the app_id is currently unavailable
        """
        if self.__fec_data._app_id is None:
            raise self.exception("app_id")
        return self.__fec_data._app_id

    def has_app_id(self):
        return self.__fec_data._app_id is not None

    # simulation_time_step_methods

    def has_time_step(self):
        """
        Check if any/all of the time_step values are known

        True When all simulation_time_step are known
        False when none of the simulation_time_step values are known.
        There is never a case when some are known and others not

        :rtype: bool
        """
        return self.__fec_data._simulation_time_step_us is not None

    def get_simulation_time_step_us(self):
        """ The simulation timestep, in microseconds or None if not known

        Previously know as "machine_time_step"

        :rtype: int or None
        """
        return self.__fec_data._simulation_time_step_us

    def get_simulation_time_step_s(self):
        """ The simulation timestep, in seconds or None if not known

        Semantic sugar for simulation_time_step_us / 1,000,000.

        :rtype: int or None
        """
        return self.__fec_data._simulation_time_step_s

    def get_simulation_time_step_ms(self):
        """ The simulation time step, in milliseconds or None if not known

        Semantic sugar for simulation_time_step_us / 1000.

        :rtype: float or None
        """
        return self.__fec_data._simulation_time_step_ms

    def get_simulation_time_step_per_ms(self):
        """ The simulation time step in a milliseconds or None if not known

        Semantic sugar for 1000 / simulation_time_step_us

        :rtype: float or None
        :raises SpinnFrontEndException:
            If the simulation_time_step is currently unavailable
        """
        return self.__fec_data._simulation_time_step_per_ms

    def get_simulation_time_step_per_s(self):
        """ The simulation time step in a seconds or None if not known

        Semantic sugar for 1,000,000 / simulation_time_step_us

        :rtype: float or None
        :raises SpinnFrontEndException:
            If the simulation_time_step is currently unavailable
        """
        return self.__fec_data._simulation_time_step_per_s

    def get_hardware_time_step_ms(self):
        """ The hardware timestep, in milliseconds or None if not known

        Semantic sugar for simulation_time_step_ms * time_scale_factor

        :rtype: float or None
        """
        return self.__fec_data._hardware_time_step_ms

    def get_hardware_time_step_us(self):
        """ The hardware timestep, in microeconds or None if not known

        Semantic sugar for simulation_time_step_us * time_scale_factor

        :rtype: int or None
        """
        return self.__fec_data._hardware_time_step_us

    @property
    def simulation_time_step_us(self):
        """ The simulation time step, in microseconds

        Previously known as machine_timestep

        :rtype: int
        :raises SpinnFrontEndException:
            If the simulation_time_step is currently unavailable
        """
        if self.__fec_data._simulation_time_step_us is None:
            raise self.exception("simulation_time_step_us")
        return self.__fec_data._simulation_time_step_us

    @property
    def simulation_time_step_ms(self):
        """ The simulation timestep, in microseconds

        Semantic sugar for simulation_time_step() / 1000.

        :rtype: float
        :raises SpinnFrontEndException:
            If the simulation_time_step_ms is currently unavailable
        """
        if self.__fec_data._simulation_time_step_ms is None:
            raise self.exception("simulation_time_step_ms")
        return self.__fec_data._simulation_time_step_ms

    @property
    def simulation_time_step_per_ms(self):
        """ The simulation time steps per millisecond

        Semantic sugar for 1000 / simulation_time_step()

        :rtype: float
        :raises SpinnFrontEndException:
            If the simulation_time_step is currently unavailable
        """
        if self.__fec_data._simulation_time_step_per_ms is None:
            raise self.exception("simulation_time_step_per_ms")
        return self.__fec_data._simulation_time_step_per_ms

    @property
    def simulation_time_step_per_s(self):
        """ The simulation time steps per second

        Semantic sugar for 1,000,000 / simulation_time_step()

        :rtype: float
        :raises SpinnFrontEndException:
            If the simulation_time_step is currently unavailable
        """
        if self.__fec_data._simulation_time_step_per_s is None:
            raise self.exception("simulation_time_step_per_s")
        return self.__fec_data._simulation_time_step_per_s

    @property
    def simulation_time_step_s(self):
        """ The simulation timestep, in seconds

        Semantic sugar for simulation_time_step() / 1,000,000.

        :rtype: float
        :raises SpinnFrontEndException:
            If the simulation_time_step_ms is currently unavailable
        """
        if self.__fec_data._simulation_time_step_s is None:
            raise self.exception("simulation_time_step_s")
        return self.__fec_data._simulation_time_step_s

    @property
    def hardware_time_step_ms(self):
        """ The hardware timestep, in milliseconds

        Semantic sugar for simulation_time_step_ms * time_sclae_factor

        :rtype: float
        :raises SpinnFrontEndException:
            If the simulation_time_step is currently unavailable
        """
        if self.__fec_data._hardware_time_step_ms is None:
            raise self.exception("hardware_time_step_ms")
        return self.__fec_data._hardware_time_step_ms

    @property
    def hardware_time_step_us(self):
        """ The hardware timestep, in microseconds

        Semantic sugar for simulation_time_step_us * time_sclae_factor

        :rtype: int
        :raises SpinnFrontEndException:
            If the simulation_time_step is currently unavailable
        """
        if self.__fec_data._hardware_time_step_us is None:
            raise self.exception("ardware_time_step_us")
        return self.__fec_data._hardware_time_step_us

    # time scale factor

    def get_time_scale_factor(self):
        """
        :rtype: int, float or None
        """
        return self.__fec_data._time_scale_factor

    @property
    def time_scale_factor(self):
        """

        :rtype: int or float
        :raises SpinnFrontEndException:
            If the time_scale_factor is currently unavailable
        """
        if self.__fec_data._time_scale_factor is None:
            raise self.exception("time_scale_factor")
        return self.__fec_data._time_scale_factor

    def has_time_scale_factor(self):
        """

        :rtype: bool
        """
        return self.__fec_data._time_scale_factor is not None

    # n calls_to run

    # The data the user gets needs not be the exact data cached
    def get_n_calls_to_run(self):
        """
        The number of this or the next call to run or None if not Known

        :rtpye: int
        """
        try:
            if self.__fec_data._status == Data_Status.IN_RUN:
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
            raise self.exception("n_calls_to_run")
        if self.__fec_data._status == Data_Status.IN_RUN:
            return self.__fec_data._n_calls_to_run
        else:
            # This is the current behaviour in ASB
            return self.__fec_data._n_calls_to_run + 1

    def has_n_calls_to_run(self):
        return self.__fec_data._n_calls_to_run is not None

    # Report directories
    def get_report_default_directory(self):
        return self.__fec_data._report_default_directory

    @property
    def report_default_directory(self):
        if self.__fec_data._report_default_directory is None:
            raise self.exception("report_default_directory")
        return self.__fec_data._report_default_directory

    def has_report_default_directory(self):
        return self.__fec_data._report_default_directory is not None

    def get_provenance_file_path(self):
        return self.__fec_data._provenance_file_path

    @property
    def provenance_file_path(self):
        if self.__fec_data._provenance_file_path is None:
            raise self.exception("provenance_file_path")
        return self.__fec_data._provenance_file_path

    def has_provenance_file_path(self):
        return self.__fec_data._provenance_file_path is not None

    # Stuff to support inject_items

    def __getitem__(self, item):
        """
        Provides dict style access to the key data.

        Allow this class to be passed into the inject_items method.
        May be removed when inject_items removed.

        Values exposed this way are currently limited to the ones needed for
        injection

        :param str item: key to object wanted
        :return: Object asked for
        :rtype: Object
        :raise KeyError: the error message will say if the item is not known
            now or not provided
        """
        value = self._unchecked_getitem(item)
        if value is None:
            raise KeyError(f"Item {item} is currently not set")
        return value

    def __contains__(self, item):
        """
        Provides dict style in checks to the key data.

        Allow this class to be passed into the inject_items method.
        May be removed when inject_items removed.

        Keys check this way are limited to the ones needed for injection

        :param str item:
        :return: True if the items is currently know
        :rtype: bool
        """
        if self._unchecked_getitem(item) is not None:
            return True
        return False

    def items(self):
        """
        Lists the keys of the data currently available.

        Allow this class to be passed into the inject_items method.
        May be removed when inject_items removed.

        Keys exposed this way are limited to the ones needed for injection

        :return: List of the keys for which there is data
        :rtype: list(str)
        :raise KeyError:  Amethod this call depends on could raise this
            exception, but that indicates a programming mismatch
        """
        results = []
        for key in ["APPID", "ApplicationGraph", "DataInMulticastKeyToChipMap",
                    "DataInMulticastRoutingTables", "DataNTimeSteps",
                    "ExtendedMachine", "FirstMachineTimeStep", "MachineGraph",
                    "MachinePartitionNKeysMap", "Placements", "RoutingInfos",
                    "RunUntilTimeSteps", "SystemMulticastRouterTimeoutKeys",
                    "Tags"]:
            item = self._unchecked_getitem(key)
            if item is not None:
                results.append((key, item))
        return results

    def _unchecked_getitem(self, item):
        """
        Returns the data for this item or None if currently unknown.

        Allow this class to be passed into the inject_items method.
        May be removed when inject_items removed.

        Values exposed this way are limited to the ones needed for injection

        :param str item:
        :return: The value for this item or None is currently unkwon
        :rtype: Object or None
        :raise KeyError: It the item is one that is never provided
        """
        if item == "APPID":
            if self.has_app_id():
                return self.app_id
            else:
                return None

        # TODO Actually add these items to this code

        """
        if item == "ApplicationGraph":
            return self.__application_graph
        if item == "DataInMulticastKeyToChipMap":
            return self.__data_in_multicast_key_to_chip_map
        if item == "DataInMulticastRoutingTables":
            return self.__data_in_multicast_routing_tables
        if item == "DataNTimeSteps":
            return self.__max_run_time_steps
        if item == "DataNSteps":
            return self.__max_run_time_steps
        if item == "ExtendedMachine":
            return self.__machine
        if item == "FirstMachineTimeStep":
            return self.__first_machine_time_step
        if item == "MachineGraph":
            return self.__machine_graph
        if item == "MachinePartitionNKeysMap":
            return self.__machine_partition_n_keys_map
        if item == "Placements":
            return self.__placements
        if item == "RoutingInfos":
            return self.__routing_infos
        if item == "RunUntilTimeSteps":
            return self.__current_run_timesteps
        if item == "SystemMulticastRouterTimeoutKeys":
            return self.__system_multicast_router_timeout_keys
        if item == "Tags":
            return self.__tags
        """

        raise KeyError(f"Unexpected Item {item}")
