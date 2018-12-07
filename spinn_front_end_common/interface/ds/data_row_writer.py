from spinn_utilities.overrides import overrides
from spinn_storage_handlers.abstract_classes import (
    AbstractDataWriter, AbstractContextManager)


class DataRowWriter(AbstractDataWriter, AbstractContextManager):
    __slots__ = [
        "_x",
        "_y",
        "_p",
        "_targets",
        "_data"

    ]

    def __init__(self, x, y, p, targets):
        self._x = x
        self._y = y
        self._p = p
        self._targets = targets
        self._data = bytearray()

    @overrides(AbstractDataWriter.write)
    def write(self, data):
        self._data += data

    @overrides(AbstractDataWriter.tell)
    def tell(self):
        raise NotImplementedError(
            "https://github.com/SpiNNakerManchester/SpiNNStorageHandlers/"
            "issues/26")

    @overrides(AbstractContextManager.close, extend_doc=False)
    def close(self):
        """ Closes the file.

        :rtype: None
        :raise spinn_storage_handlers.exceptions.DataWriteException: \
            If the file cannot be closed
        """
        self._targets.write_data_spec(self._x, self._y, self._p, self._data)
