class DataWritten(object):
    """ Describes data written to SpiNNaker.
    """

    __slots__ = [
        "_memory_used", "_memory_written", "_start_address"]

    def __init__(self, start_address, memory_used, memory_written):
        self._start_address = start_address
        self._memory_used = memory_used
        self._memory_written = memory_written

    @property
    def memory_used(self):
        return self._memory_used

    @property
    def start_address(self):
        return self._start_address

    @property
    def memory_written(self):
        return self._memory_written

    def __eq__(self, other):
        if not isinstance(other, DataWritten):
            return False
        return (self._start_address == other.start_address and
                self._memory_used == other.memory_used and
                self._memory_written == other.memory_written)
