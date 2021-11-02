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
from spinn_front_end_common.utilities.constants import (
    MICRO_TO_MILLISECOND_CONVERSION)


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
        "_machine_time_step",
        "_provenance_file_path",
        "_machine_time_step_ms",
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
        Clears out all data returns to the NOT_SETUP state
        """
        self._app_id = None
        self._machine_time_step = None
        self._provenance_file_path = None
        self._n_calls_to_run = None
        self._machine_time_step_ms = None
        self._report_default_directory = None
        self._time_scale_factor = None


class FecDataView(object):
    """
    A read only view of the data available at FEC level

    The property methods will either return a valid value or
    raise an Exception if the data is currently not available

    While how and where the underpinning DataModel(s) store data can change
    without notice, methods in this class can be considered a supported API
    """

    __fec_data = _FecDataModel()
    __slots__ = []

    @property
    def status(self):
        return self.__fec_data._status

    @property
    def app_id(self):
        """
        The current application id

        :rtype: int
        :raises SpinnFrontEndException:
            If the app_id is currently unavailable
        """
        if self.__fec_data._app_id is None:
            raise self.status.exception("machine_time_step")
        return self.__fec_data._app_id

    def has_app_id(self):
        return self.__fec_data._app_id is not None

    @property
    def machine_time_step(self):
        """ The machine timestep, in microseconds

        :rtype: int
        :raises SpinnFrontEndException:
            If the machine_time_step is currently unavailable
        """
        if self.__fec_data._machine_time_step is None:
            raise self.status.exception("machine_time_step")
        return self.__fec_data._machine_time_step

    def has_machine_time_step(self):
        return self.__fec_data._machine_time_step is not None

    @property
    def machine_time_step_ms(self):
        """ The machine timestep, in microseconds

        Semantic sugar for machine_time_step() / 1000.

        :rtype: float
        :raises SpinnFrontEndException:
            If the machine_time_step_ms is currently unavailable
        """
        if self.__fec_data._machine_time_step_ms is None:
            raise self.status.exception("machine_time_step_ms")
        return self.__fec_data._machine_time_step_ms

    def has_machine_time_step_ms(self):
        return self.__fec_data._machine_time_step_ms is not None

    # semantic sugar without caching
    @property
    def machine_time_step_per_ms(self):
        """ The machine timesteps in a microseconds

        Semantic sugar for 1000 / machine_time_step()

        :rtype: float
        :raises SpinnFrontEndException:
            If the machine_time_step is currently unavailable
        """
        return MICRO_TO_MILLISECOND_CONVERSION / self.machine_time_step

    def has_machine_time_step_per_ms(self):
        return self.__fec_data._machine_time_step is not None

    # The data the user gets needs not be the exact data cached
    @property
    def n_calls_to_run(self):
        """
        The number of this or the next call to run

        :rtpye: int
        """
        if self.__fec_data._n_calls_to_run is None:
            raise self.status.exception("n_calls_to_run")
        if self.__fec_data._status == Data_Status.IN_RUN:
            return self.__fec_data._n_calls_to_run
        else:
            # This is the current behaviour in ASB
            return self.__fec_data._n_calls_to_run + 1

    @property
    def report_default_directory(self):
        if self.__fec_data._report_default_directory is None:
            raise self.status.exception("report_default_directory")
        return self.__fec_data._report_default_directory

    @property
    def provenance_file_path(self):
        if self.__fec_data._provenance_file_path is None:
            raise self.status.exception("provenance_file_path")
        return self.__fec_data._provenance_file_path

    def __getitem__(self, item):
        """
        Provides dict style access to the key data.

        Allow this class to be passed into the do_injection method

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
