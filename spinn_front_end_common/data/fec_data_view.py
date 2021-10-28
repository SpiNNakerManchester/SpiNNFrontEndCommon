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
