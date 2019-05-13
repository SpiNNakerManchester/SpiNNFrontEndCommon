from spinn_utilities.overrides import overrides
from spinn_storage_handlers.abstract_classes import (
    AbstractDataReader, AbstractContextManager)


class DataRowReader(AbstractDataReader, AbstractContextManager):
    __slots__ = [
        "_index",
        "_data",
    ]

    def __init__(self, data):
        self._index = 0
        self._data = data

    @overrides(AbstractDataReader.read)
    def read(self, n_bytes):
        previous = self._index
        self._index += n_bytes
        return self._data[previous:self._index]

    @overrides(AbstractDataReader.readall)
    def readall(self):
        previous = self._index
        self._index = len(self._data)
        return self._data[previous:self._index]

    @overrides(AbstractDataReader.readinto)
    def readinto(self, data):
        raise NotImplementedError(
            "https://github.com/SpiNNakerManchester/SpiNNStorageHandlers/"
            "issues/26")

    @overrides(AbstractDataReader.tell)
    def tell(self):
        raise NotImplementedError(
            "https://github.com/SpiNNakerManchester/SpiNNStorageHandlers/"
            "issues/26")

    @overrides(AbstractContextManager.close, extend_doc=False)
    def close(self):
        """ Does Nothing """

    def __eq__(self, other):
        """ Equality mainly for testing.
        """
        # pylint: disable=protected-access
        if not isinstance(other, DataRowReader):
            return False
        return self._data == other._data

    def __ne__(self, other):
        if not isinstance(other, DataRowReader):
            return True
        return not self.__eq__(other)
