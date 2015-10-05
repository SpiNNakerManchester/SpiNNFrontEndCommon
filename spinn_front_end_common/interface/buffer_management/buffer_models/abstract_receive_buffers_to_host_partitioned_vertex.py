"""
AbstractReceiveBuffersToHostPartitionedVertex
"""

# general imports
from abc import ABCMeta
from abc import abstractmethod
from six import add_metaclass
import logging

logger = logging.getLogger(__name__)


@add_metaclass(ABCMeta)
class AbstractReceiveBuffersToHostPartitionedVertex(object):
    """ Interface to a partitioned vertex that buffers information to be
        sent to the host
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