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
from spinn_utilities.config_holder import get_config_int
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.utilities.constants import (
    MICRO_TO_MILLISECOND_CONVERSION)
from .data_status import Data_Status
from .fec_data_view import FecDataView

logger = FormatAdapter(logging.getLogger(__name__))


class FecDataWriter(FecDataView):
    """
    Writer class for the Fec Data

    """
    def setup(self):
        """
        Clears out all data
        :return:
        """
        self._fec_data._FecDataModel__clear()
        self._fec_data._FecDataModel__n_calls_to_run = 0
        self._fec_data._FecDataModel__status = Data_Status.SETUP
        self.__set_up_report_specifics()

    def start_run(self):
        self._fec_data._FecDataModel__n_calls_to_run += 1
        self._fec_data._FecDataModel__status = Data_Status.IN_RUN

    def finish_run(self):
        self._fec_data._FecDataModel__status = Data_Status.FINISHED

    def __set_up_report_specifics(self):
        """
        :param int n_calls_to_run:
            the counter of how many times run has been called.
        """
        # This is a highly simplified example
        report_simulation_top_directory = os.getcwd()
        self._fec_data._FecDataModel__report_default_directory = os.path.join(
            report_simulation_top_directory, f"run_{self.n_calls_to_run}")
        logger.info(self.report_default_directory)
        self._fec_data._FecDataModel__provenance_file_path = os.path.join(
            self._fec_data._FecDataModel__report_default_directory,
            "provenance_data")

    def set_machine_time_step(self, machine_time_step):
        if machine_time_step is None:
            machine_time_step = get_config_int("Machine", "machine_time_step")
        self._fec_data._FecDataModel__machine_time_step = machine_time_step
        self._fec_data._FecDataModel__machine_time_step_ms = (
                machine_time_step / MICRO_TO_MILLISECOND_CONVERSION)
