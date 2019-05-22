try:
    from collections import MutableMapping
except ImportError:
    from UserDict import DictMixin as MutableMapping
from .data_row_writer import DataRowWriter
from .data_row_reader import DataRowReader
from .ds_sqllite_database import DsSqlliteDatabase


class DataSpecificationTargets(MutableMapping):

    __slots__ = ["_db"]

    def __init__(self, machine, report_folder, init=True):
        """
        :param machine:
        :type machine: :py:class:`spinn_machine.Machine`
        :param report_folder:
        """
        # real DB would write to report_folder
        self._db = DsSqlliteDatabase(machine, report_folder, init)

    def __getitem__(self, core):
        """
        Implements the mapping __getitem__ as long as core is the right type.

        :param core:triple of (x, y, p)
        :type core: (int, int, int)
        :rtype: dict() with the keys
            'start_address', 'memory_used' and 'memory_written'
        """
        (x, y, p) = core
        return DataRowReader(self._db.get_ds(x, y, p))

    def __setitem__(self, core, info):
        raise NotImplementedError(
            "Direct set not supported. See create_data_spec")

    def __delitem__(self, core):
        raise NotImplementedError("Delete not supported")

    def keys(self):
        """
        Yields the keys.

        As the more typical call is iteritems this makes use of that

        :return:
        """
        for key, _value in self._db.ds_iteritems():
            yield key

    __iter__ = keys

    def __len__(self):
        """
        TEMP implementation

        :return:
        """
        return self._db.ds_n_cores()

    n_targets = __len__

    def create_data_spec(self, x, y, p):
        return DataRowWriter(x, y, p, self)

    def write_data_spec(self, x, y, p, ds):
        self._db.save_ds(x, y, p, ds)

    def items(self):
        for key, value in self._db.ds_iteritems():
            yield key, DataRowReader(value)

    # Python 2 backward compatibility
    iteritems = items

    def get_database(self):
        """ Expose the database so it can be shared

        :rtype:
            py:class:`spinn_front_end_common.interface.ds.DsAbstractDatabase`
        """
        return self._db

    def set_app_id(self, app_id):
        """ Sets the same app_id for all rows that have DS content

        :param app_id: value to set
        :rtype app_id: int
        """
        self._db.ds_set_app_id(app_id)

    def get_app_id(self, x, y, p):
        """ Gets the app_id set for this core

        :param x: core x
        :param y: core y
        :param p: core p
        :rtype: int
        """
        return self._db.ds_get_app_id(x, y, p)
