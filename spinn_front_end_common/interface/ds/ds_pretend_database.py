from six import iteritems
from spinn_utilities.overrides import overrides
from .ds_abstact_database import DsAbstractDatabase


class DsPretendDatabase(DsAbstractDatabase):
    __slots__ = ["_ds_temp", "_info_temp"]

    def __init__(self):
        self._ds_temp = dict()
        self._info_temp = dict()

    @overrides(DsAbstractDatabase.close)
    def close(self):
        """
            close the database
        """

    @overrides(DsAbstractDatabase.save_ds)
    def save_ds(self, core_x, core_y, core_p, ds):
        # In the database map the core to the board using ethernet x and y
        self._ds_temp[(core_x, core_y, core_p)] = ds

    @overrides(DsAbstractDatabase.get_ds)
    def get_ds(self, x, y, p):
        return self._ds_temp[(x, y, p)]

    @overrides(DsAbstractDatabase.ds_iteritems)
    def ds_iteritems(self):
        return iteritems(self._ds_temp)

    @overrides(DsAbstractDatabase.ds_n_cores)
    def ds_n_cores(self):
        return len(self._ds_temp)

    @overrides(DsAbstractDatabase.get_write_info)
    def get_write_info(self, x, y, p):
        return self._info_temp[(x, y, p)]

    @overrides(DsAbstractDatabase.set_write_info)
    def set_write_info(self, x, y, p, info):
        self._info_temp[(x, y, p)] = info

    @overrides(DsAbstractDatabase.info_n_cores)
    def info_n_cores(self):
        return len(self._info_temp)

    @overrides(DsAbstractDatabase.info_iteritems)
    def info_iteritems(self):
        return iteritems(self._info_temp)
