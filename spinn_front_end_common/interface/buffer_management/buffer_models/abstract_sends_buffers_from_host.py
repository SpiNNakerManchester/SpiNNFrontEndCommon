# general imports
import logging
from six import add_metaclass

from spinn_utilities.abstract_base import AbstractBase, abstractmethod

logger = logging.getLogger(__name__)


@add_metaclass(AbstractBase)
class AbstractSendsBuffersFromHost(object):
    """ Interface to an object that sends buffers of keys to be\
        transmitted at given timestamps in the simulation
    """

    __slots__ = ()

    @abstractmethod
    def buffering_input(self):
        """ Return True if the input of this vertex is to be buffered
        """

    @abstractmethod
    def get_regions(self):
        """ Get the set of regions for which there are keys to be sent

        :return: Iterable of region ids
        :rtype: iterable of int
        """

    @abstractmethod
    def get_region_buffer_size(self, region):
        """ Get the size of the buffer to be used in SDRAM on the machine\
            for the region in bytes

        :param region: The region to get the buffer size of
        :type region: int
        :return: The size of the buffer space in bytes
        :rtype: int
        """

    @abstractmethod
    def get_max_buffer_size_possible(self, region):
        """ Gets the max possible size of a buffered region

        :param region: the region to find the max possible size of
        :type region: int
        :return: the max possible size of the buffered region
        :rtype: int
        """

    @abstractmethod
    def is_next_timestamp(self, region):
        """ Determine if there is another timestamp with data to be sent

        :param region: The region to determine if there is more data for
        :type region: int
        :return: True if there is more data, False otherwise
        :rtype: int
        """

    @abstractmethod
    def get_next_timestamp(self, region):
        """ Get the next timestamp at which there are still keys to be sent\
            for the given region

        :param region: The region to get the timestamp for
        :type region: int
        :return: The timestamp of the next available keys
        :rtype: int
        """

    @abstractmethod
    def is_next_key(self, region, timestamp):
        """ Determine if there are still keys to be sent at the given\
            timestamp for the given region

        :param region: The region to determine if there are keys for
        :type region: int
        :param timestamp: The timestamp to determine if there are more keys for
        :type timestamp: int
        :return: True if there are more keys to send for the parameters, False\
                    otherwise
        :rtype: bool
        """

    @abstractmethod
    def get_next_key(self, region):
        """ Get the next key in the given region

        :param region: The region to get the next key from
        :type region: int
        :return: The next key, or None if there are no more keys
        :rtype: int
        """

    @abstractmethod
    def is_empty(self, region):
        """ Return true if there are no spikes to be buffered for the\
            specified region

        :param region: The region to get the next key from
        :type region: int
        :return: True if there are no keys to send for the region, False\
                    otherwise
        :rtype: bool
        """

    @abstractmethod
    def rewind(self, region):
        """ Rewinds the internal buffer in preparation of re-sending
            the spikes

        :param region: The region to rewind
        :type region: int
        """
