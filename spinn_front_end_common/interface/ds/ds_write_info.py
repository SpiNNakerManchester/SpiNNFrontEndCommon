try:
    from collections import MutableMapping
except ImportError:
    from UserDict import DictMixin as MutableMapping


class DsWriteInfo(MutableMapping):

    __slots__ = ["_db"]

    def __init__(self, database):
        """

        :param database: Database to map
        :type database:
            py:class:`spinn_front_end_common.interface.ds.DsAbstractDatabase`
        """
        self._db = database

    def __getitem__(self, core):
        """
        Implements the mapping __getitem__ as long as core is the right type
        :param core:triple of (x, y, p)
        :type core: (int, int, int)
        :rtype: dict() with the keys
            'start_address', 'memory_used' and 'memory_written'
        """
        (x, y, p) = core
        return self.get_info(x, y, p)

    def get_info(self, x, y, p):
        """
        gets the info for the core x, y, p

        :param x: core x
        :param y: core y
        :param p: core p
        :rtype: dict() with the keys
            'start_address', 'memory_used' and 'memory_written'
        """
        return self._db.get_write_info(x, y, p)

    def __setitem__(self, core, info):
        (x, y, p) = core
        self.set_info(x, y, p, info)

    def set_info(self, x, y, p, info):
        """
        Sets the info for the core x, y, p

        :param x: core x
        :param y: core y
        :param p: core p
        :param info: dict() with the keys
            'start_address', 'memory_used' and 'memory_written'
        """
        self._db.set_write_info(x, y, p, info)

    def clear_write_info(self):
        """
        Clears the info for all cores
        """
        self._db.clear_write_info()

    def __delitem__(self):
        raise NotImplementedError("Delete not supported")

    def keys(self):
        """
        Yields the keys.

        As the more typical call is iteritems this makes use of that
        :return:
        """
        for key, value in self._db.info_iteritems():
            yield key

    __iter__ = keys

    def __len__(self):
        """
        TEMP implementation

        :return:
        """
        return self._db.info_n_cores()

    def items(self):
        return self._db.info_iteritems()

    # Python 2 backward compatibility
    iteritems = items
