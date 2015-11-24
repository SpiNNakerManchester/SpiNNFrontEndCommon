# general imports
from abc import ABCMeta
from abc import abstractmethod
from six import add_metaclass
import logging

logger = logging.getLogger(__name__)


@add_metaclass(ABCMeta)
class AbstractBufferedDataStorage(object):
    """ An object that can store and read back buffered data
    """

    @abstractmethod
    def write(self, data):
        pass

    @abstractmethod
    def read(self, data_size):
        pass

    @abstractmethod
    def read_all(self):
        pass

    @abstractmethod
    def seek_read(self, offset, whence=0):
        pass

    @abstractmethod
    def seek_write(self, offset, whence=0):
        pass

    @abstractmethod
    def tell_read(self):
        pass

    @abstractmethod
    def tell_write(self):
        pass

    @abstractmethod
    def eof(self):
        pass
