from six import iteritems
from spinn_utilities.overrides import overrides
from .ds_abstact_database import DsAbstractDatabase


class DsPretendDatabase(DsAbstractDatabase):
    __slots__ = ["_ds_temp"]

    def __init__(self):
        self._ds_temp = dict()

    def commit(self):
        """
            database may need to commit data here
        """

    @overrides(DsAbstractDatabase.close)
    def close(self):
        """
            close the database
        """

    @overrides(DsAbstractDatabase.save_board)
    def save_board(self, ethernet_chip):
        """
            The ds would create a board row here
        """

    @overrides(DsAbstractDatabase.save_ds)
    def save_ds(self, core_x, core_y, core_p, ethernet_x, ethernet_y, ds):
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
        """
        Gets the provenance returned by the Data Spec executor

        :param x: core x
        :param y: core y
        :param p: core p
        :rtype: dict() with the keys
            'start_address', 'memory_used' and 'memory_written'
        """
