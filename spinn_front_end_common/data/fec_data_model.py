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

from spinn_front_end_common.data.data_status import Data_Status


class FecDataModel(object):
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
        "__app_id",
        "__machine_time_step",
        "__provenance_file_path",
        "__machine_time_step_ms",
        "__n_calls_to_run",
        "__report_default_directory",
        "__time_scale_factor",
        # Data status mainly to raise best Exception
        "__status"
    ]

    def __new__(cls):
        if cls.__singleton:
            return cls.__singleton
        # pylint: disable=protected-access
        obj = object.__new__(cls)
        cls.__singleton = obj
        obj.__clear()
        return obj

    def __clear(self):
        """
        Clears out all data returns to the NOT_SETUP state
        """
        self.__app_id = None
        self.__machine_time_step = None
        self.__provenance_file_path = None
        self.__n_calls_to_run = None
        self.__machine_time_step_ms = None
        self.__report_default_directory = None
        self.__time_scale_factor = None
        self.__status = Data_Status.NOT_SETUP
