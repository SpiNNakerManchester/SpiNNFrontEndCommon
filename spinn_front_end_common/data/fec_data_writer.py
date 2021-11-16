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

import logging
import os
import tempfile
from spinn_utilities.config_holder import get_config_int
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.utilities.constants import (
    MICRO_TO_MILLISECOND_CONVERSION)
from .data_status import Data_Status
from .fec_data_view import FecDataView, _FecDataModel

logger = FormatAdapter(logging.getLogger(__name__))
__temp_dir = None


class FecDataWriter(FecDataView):
    """
    Writer class for the Fec Data

    """
    __fec_data = _FecDataModel()
    __slots__ = []

    def mock(self):
        """
        Clears out all data and adds mock values where needed.

        This should set the most likely defaults values.
        But be aware that what is considered the most likely default could
        change over time.

        Unittests that depend on any valid value being set should be able to
        depend on Mock.

        Unittest that depend on a specific value should call mock and then
        set that value.
        """
        self.__fec_data._clear()
        self.__fec_data._n_calls_to_run = 0
        self.__fec_data._status = Data_Status.MOCKED
        self.__set_up_report_mocked()
        self.set_app_id(6)
        self.set_machine_time_step(1000)

    def setup(self):
        """
        Puts all data back into the state expected at sim.setup time

        """
        self.__fec_data._clear()
        self.__fec_data._n_calls_to_run = 0
        self.__fec_data._status = Data_Status.SETUP
        self.__set_up_report_specifics()

    def start_run(self):
        self.__fec_data._n_calls_to_run += 1
        self.__fec_data._status = Data_Status.IN_RUN

    def finish_run(self):
        self.__fec_data._status = Data_Status.FINISHED

    def __set_up_report_mocked(self):
        """
        Sets all the directories used to a Temporary Directory
        """
        temp_dir = tempfile.TemporaryDirectory()

        self.__fec_data._report_default_directory = temp_dir
        self.__fec_data._provenance_file_path = temp_dir

    def __set_up_report_specifics(self):
        # This is a highly simplified example
        report_simulation_top_directory = os.getcwd()
        self.__fec_data._report_default_directory = os.path.join(
            report_simulation_top_directory, f"run_{self.n_calls_to_run}")
        logger.info(self.report_default_directory)
        self.__fec_data._provenance_file_path = os.path.join(
            self.__fec_data._report_default_directory,
            "provenance_data")

    def set_app_id(self, app_id):
        """
        Sets the app_id value

        :param int app_id: new value
        """
        if not isinstance(app_id, int):
            raise TypeError("app_id should be an int")
        self.__fec_data._app_id = app_id

    def set_machine_time_step(self, machine_time_step):
        if machine_time_step is None:
            machine_time_step = get_config_int("Machine", "machine_time_step")
        self.__fec_data._machine_time_step = machine_time_step
        self.__fec_data._machine_time_step_ms = (
                machine_time_step / MICRO_TO_MILLISECOND_CONVERSION)
