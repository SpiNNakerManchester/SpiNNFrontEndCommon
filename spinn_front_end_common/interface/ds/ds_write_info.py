try:
    from collections import MutableMapping
except ImportError:
    from UserDict import DictMixin as MutableMapping


class DsWriteInfo(MutableMapping):

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
        (x, y, p) = core
        return self.getInfo(x, y, p)

    def __setitem__(self, core, info):
        (x, y, p) = core
        self.setInfo(x, y, p, info)

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

    def getInfo(self, x, y, p):
        """
        TEMP implementation
        :param x: core x
        :param y: core y
        :param p: core p
        :return:
        """
        return self._temp[(x, y, p)]

    def setInfo(self, x, y, p, info):
        """
        TEMP implementation
        :param x: core x
        :param y: core y
        :param p: core p
        :param info:
        :return:
        """
        self._temp[(x, y, p)] = info
