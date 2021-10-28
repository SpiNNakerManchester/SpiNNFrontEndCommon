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


"""   
     # Data values cached
        #"__app_provenance_file_path",
        "__machine_time_step",
        "__provenance_file_path",
        "__machine_time_step_ms",
        #"__machine_time_step_per_ms",
        "__report_default_directory",
        "__time_scale_factor",
        #
        "__status"


    def machine_time_step(self, new_value):
#        self.__machine_time_step = new_value
#        self.__machine_time_step_ms = (
#                new_value / MICRO_TO_MILLISECOND_CONVERSION)
#        self.__machine_time_step_per_ms = (
#                MICRO_TO_MILLISECOND_CONVERSION / new_value)

"""