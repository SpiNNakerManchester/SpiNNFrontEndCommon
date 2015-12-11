# general imports
from abc import ABCMeta
from abc import abstractmethod
from six import add_metaclass

import os
import logging


logger = logging.getLogger(__name__)


@add_metaclass(ABCMeta)
class AbstractBufferedDataStorage(object):
    """ An object that can store and read back buffered data
    """

    @abstractmethod
    def write(self, data):
        """ Store data in the bytearray buffer in the position indicated by\
            the write pointer index

        :param data: the data to be stored
        :type data: bytearray
        :return: None
        :rtype: None
        """
        pass

    @abstractmethod
    def read(self, data_size):
        """ Read data from the bytearray buffer from the position indicated by\
            the read pointer index

        :param data_size: number of bytes to be read
        :type data_size: int
        :return: a bytearray containing the data read
        :rtype: bytearray
        """
        pass

    @abstractmethod
    def read_all(self):
        """ Read all the data contained in the bytearray buffer starting from\
            position 0 to the end

        :return: a bytearray containing the data read
        :rtype: bytearray
        """
        pass

    @abstractmethod
    def seek_read(self, offset, whence=os.SEEK_SET):
        """ Set the buffer's current read position to the offset

        :param offset: Position of the read pointer within the buffer
        :type offset: int
        :param whence: One of:
                * os.SEEK_SET which means absolute buffer positioning (default)
                * os.SEEK_CUR which means seek relative to the current\
                  read position
                * os.SEEK_END which means seek relative to the buffer's end
        :return: None
        :rtype: None
        """
        pass

    @abstractmethod
    def seek_write(self, offset, whence=os.SEEK_SET):
        """ Set the buffer's current write position to the offset

        :param offset: Position of the write pointer within the buffer
        :type offset: int
        :param whence: One of:
                * os.SEEK_SET which means absolute buffer positioning (default)
                * os.SEEK_CUR which means seek relative to the current\
                  write position
                * os.SEEK_END which means seek relative to the buffer's end
        :return: None
        :rtype: None
        """
        pass

    @abstractmethod
    def tell_read(self):
        """ The current position of the read pointer

        :return: The current position of the read pointer
        :rtype: int
        """
        pass

    @abstractmethod
    def tell_write(self):
        """ The current position of the write pointer

        :return: The current position of the write pointer
        :rtype: int
        """
        pass

    @abstractmethod
    def eof(self):
        """ Check if the read pointer is a the end of the buffer

        :return: True if the read pointer is at the end of the buffer,\
                 False otherwise
        :rtype: bool
        """
        pass
