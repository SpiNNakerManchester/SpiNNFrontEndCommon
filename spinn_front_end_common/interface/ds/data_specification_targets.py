from six import iteritems
try:
    from collections import MutableMapping
except ImportError:
    from UserDict import DictMixin as MutableMapping
from .data_row_writer import DataRowWriter
from .data_row_reader import DataRowReader


class DataSpecificationTargets(MutableMapping):

    def __init__(self):
        self._temp = dict()

    def __getitem__(self, core):
        """
        Implements the mapping __getitem__ as long as core is the right type
        :param core:triple of (x, y, p)
        :type core: (int, int, int)
        :rtype: dict() with the keys
            'start_address', 'memory_used' and 'memory_written'
        """
        return DataRowReader(self._temp[core])

    def __setitem__(self, core, info):
        (x, y, p) = core
        self.write(x, y, p, info)

    def __delitem__(self):
        raise NotImplementedError("Delete not supported")

    def keys(self):
        """
        TEMP implementation

        :return:
        """
        return self._temp.keys()

    def __len__(self):
        """
        TEMP implementation

        :return:
        """
        return len(self._temp)

    def __iter__(self):
        """
        TEMP implementation

        :return:
        """
        return self._temp.__iter__()

    def create_data_spec(self, x, y, p):
        return DataRowWriter(x, y, p, self)

    def write(self, x, y, p, data):
        self._temp[(x, y, p)] = data

    def n_targets(self):
        return len(self)

    def items(self):
        for key, value in iteritems(self._temp):
            yield key, DataRowReader(value)

    # Python 2 backward compatibility
    iteritems = items

