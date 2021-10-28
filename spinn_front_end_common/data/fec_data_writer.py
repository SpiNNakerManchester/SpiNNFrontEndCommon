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
from .fec_data_view import FecDataView
from spinn_front_end_common.utilities.constants import (
    MICRO_TO_MILLISECOND_CONVERSION)


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
        self._fec_data._FecDataModel__status = Data_Status.SETUP

    def set_machine_time_step(self, new_value):
        self._fec_data._FecDataModel__machine_time_step = new_value
        self._fec_data._FecDataModel__machine_time_step_ms = (
                new_value / MICRO_TO_MILLISECOND_CONVERSION)
