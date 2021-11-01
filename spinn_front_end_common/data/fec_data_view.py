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

from .fec_data_model import FecDataModel
from .data_status import Data_Status
from spinn_front_end_common.utilities.constants import (
    MICRO_TO_MILLISECOND_CONVERSION)


class FecDataView(object):
    """
    A read only view of the data available at FEC level

    The property methods will either return a valid value or
    raise an Exception if the data is currently not available

    While how and where the underpinning DataModel(s) store data can change
    without notice, methods in this class can be considered a supported API
    """

    _fec_data = FecDataModel()

    __slots__ = []

    @property
    def status(self):
        return self._fec_data._FecDataModel__status

    @property
    def machine_time_step(self):
        """ The machine timestep, in microseconds

        :rtype: int
        :raises SpinnFrontEndException:
            If the machine_time_step is currently unavailable
        """
        if self._fec_data._FecDataModel__machine_time_step is None:
            raise self.status.exception("machine_time_step")
        return self._fec_data._FecDataModel__machine_time_step

    def has_machine_time_step(self):
        return self._fec_data._FecDataModel__machine_time_step is not None

    @property
    def machine_time_step_ms(self):
        """ The machine timestep, in microseconds

        Semantic sugar for machine_time_step() / 1000.

        :rtype: float
        :raises SpinnFrontEndException:
            If the machine_time_step_ms is currently unavailable
        """
        if self._fec_data._FecDataModel__machine_time_step_ms is None:
            raise self.status.exception("machine_time_step_ms")
        return self._fec_data._FecDataModel__machine_time_step_ms

    def has_machine_time_step_ms(self):
        return self._fec_data._FecDataModel__machine_time_step_ms is not None

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
        return self._fec_data._FecDataModel__machine_time_step is not None

    # The data the user gets needs not be the exact data cached
    @property
    def n_calls_to_run(self):
        """
        The number of this or the next call to run

        :rtpye: int
        """
        if self._fec_data._FecDataModel__n_calls_to_run is None:
            raise self.status.exception("n_calls_to_run")
        if self._fec_data._FecDataModel__status == Data_Status.IN_RUN:
            return self._fec_data._FecDataModel__n_calls_to_run
        else:
            # This is the current behaviour in ASB
            return self._fec_data._FecDataModel__n_calls_to_run + 1

    @property
    def report_default_directory(self):
        if self._fec_data._FecDataModel__report_default_directory is None:
            raise self.status.exception("report_default_directory")
        return self._fec_data._FecDataModel__report_default_directory

    @property
    def provenance_file_path(self):
        if self._fec_data._FecDataModel__provenance_file_path is None:
            raise self.status.exception("provenance_file_path")
        return self._fec_data._FecDataModel__provenance_file_path

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
        value = self.__unchecked_gettiem(item)
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
        if self.__unchecked_gettiem(item) is not None:
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
            item = self.__unchecked_gettiem(key)
            if item is not None:
                results.append((key, item))
        return results

    def __unchecked_gettiem(self, item):
        """
        Returns the data for this item or None if currently unknown.

        Values exposed this way are limited to the ones needed for injection

        :param str item:
        :return: The value for this item or None is currently unkwon
        :rtype: Object or None
        :raise KeyError: It the item is one that is never provided
        """
        # TODO Actually add these items to this code

        """
        if item == "APPID":
            return self.__app_id
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
