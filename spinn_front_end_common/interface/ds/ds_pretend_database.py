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

from six import iteritems
from spinn_utilities.overrides import overrides
from spinn_front_end_common.utilities.utility_objs import DataWritten
from .ds_abstact_database import DsAbstractDatabase


class DsPretendDatabase(DsAbstractDatabase):
    __slots__ = ["_ds_temp", "_info_temp", "_app_id"]

    def __init__(self):
        self._ds_temp = dict()
        self._info_temp = dict()
        self._app_id = None

    @overrides(DsAbstractDatabase.close, extend_doc=False)
    def close(self):
        """ Close the database.
        """

    @overrides(DsAbstractDatabase.save_ds)
    def save_ds(self, core_x, core_y, core_p, ds):
        # In the database map the core to the ethernet
        self._ds_temp[core_x, core_y, core_p] = ds

    @overrides(DsAbstractDatabase.get_ds)
    def get_ds(self, x, y, p):
        return self._ds_temp[(x, y, p)]

    @overrides(DsAbstractDatabase.ds_iteritems)
    def ds_iteritems(self):
        return iteritems(self._ds_temp)

    @overrides(DsAbstractDatabase.ds_n_cores)
    def ds_n_cores(self):
        return len(self._ds_temp)

    @overrides(DsAbstractDatabase.ds_set_app_id)
    def ds_set_app_id(self, app_id):
        self._app_id = app_id

    @overrides(DsAbstractDatabase.ds_get_app_id)
    def ds_get_app_id(self, x, y, p):
        if (x, y, p) in self._ds_temp:
            return self._app_id
        return None

    @overrides(DsAbstractDatabase.get_write_info)
    def get_write_info(self, x, y, p):
        return self._info_temp[(x, y, p)]

    @overrides(DsAbstractDatabase.set_write_info)
    def set_write_info(self, x, y, p, info):
        if not isinstance(info, DataWritten):
            info = DataWritten(info["start_address"], info["memory_used"],
                               info["memory_written"])
        self._info_temp[(x, y, p)] = info

    @overrides(DsAbstractDatabase.clear_write_info)
    def clear_write_info(self):
        self._info_temp = dict()

    @overrides(DsAbstractDatabase.info_n_cores)
    def info_n_cores(self):
        return len(self._info_temp)

    @overrides(DsAbstractDatabase.info_iteritems)
    def info_iteritems(self):
        return iteritems(self._info_temp)
