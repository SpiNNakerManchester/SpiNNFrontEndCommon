# general imports
import logging
from six import add_metaclass

# spinn front end common imports
from spinn_front_end_common.interface.buffer_management.buffer_models.\
    abstract_sends_buffers_from_host import AbstractSendsBuffersFromHost

from spinn_utilities.abstract_base import AbstractBase, abstractmethod, \
    abstractproperty

logger = logging.getLogger(__name__)


@add_metaclass(AbstractBase)
class SendsBuffersFromHostPreBufferedImpl(
        AbstractSendsBuffersFromHost):
    """ Implementation of the AbstractSendsBuffersFromHost\
        which uses an existing set of buffers for the details
    """

    __slots__ = ()

    @abstractproperty
    def send_buffers(self):
        pass

    @send_buffers.setter
    @abstractmethod
    def send_buffers(self, value):
        pass

    def buffering_input(self):
        return self.send_buffers is not None

    def get_regions(self):
        """ Return the regions which has buffers to send
        """
        return self.send_buffers.keys()

    def get_max_buffer_size_possible(self, region):
        """ Return the max possible size of a buffered region

        :param region: the region to find the max possible size of
        :return: the max possible size of the buffered region
        """
        return self.send_buffers[region].max_buffer_size_possible

    def get_region_buffer_size(self, region):
        """ Return the size of a given regions buffer

        :param region: the region to find the size of
        :return: the size of the buffer
        """
        return self.send_buffers[region].buffer_size

    def is_next_timestamp(self, region):
        """ Check if there are more time stamps which need transmitting

        :param region: the region to check
        :return: boolean
        """
        return self.send_buffers[region].is_next_timestamp

    def get_next_timestamp(self, region):
        """ Return the next time stamp available in the buffered region

        :param region: the region id which is being asked
        :return: the next time stamp
        """
        return self.send_buffers[region].next_timestamp

    def is_next_key(self, region, timestamp):
        """ Check if there is more keys to transmit for a given region in a\
            given timestamp

        :param region: the region id to check
        :param timestamp:  the timestamp to check
        :return: bool
        """
        return self.send_buffers[region].is_next_key(timestamp)

    def get_next_key(self, region):
        """ Get the next key for a given region

        :param region: the region to get the next key from
        """
        return self.send_buffers[region].next_key

    def is_empty(self, region):
        """ Check if a region is empty

        :param region: the region id to check
        :return: bool
        """
        return len(self.send_buffers[region].timestamps) == 0

    def rewind(self, region):
        """ Rewinds the internal buffer in preparation of re-sending\
            the spikes

        :param region: The region to rewind
        :type region: int
        """
        self.send_buffers[region].rewind()
