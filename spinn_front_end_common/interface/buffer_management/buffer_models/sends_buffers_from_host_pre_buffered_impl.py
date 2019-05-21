import logging
from six import add_metaclass
from spinn_utilities.abstract_base import (
    AbstractBase, abstractmethod, abstractproperty)
from .abstract_sends_buffers_from_host import AbstractSendsBuffersFromHost

logger = logging.getLogger(__name__)


@add_metaclass(AbstractBase)
class SendsBuffersFromHostPreBufferedImpl(AbstractSendsBuffersFromHost):
    """ Implementation of :py:class:`AbstractSendsBuffersFromHost`\
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

    def is_next_timestamp(self, region):
        """ Check if there are more time stamps which need transmitting

        :param region: the region to check
        :return: boolean
        """
        return self.send_buffers[region].is_next_timestamp

    def get_next_timestamp(self, region):
        """ Return the next time stamp available in the buffered region

        :param region: the region ID which is being asked
        :return: the next time stamp
        """
        return self.send_buffers[region].next_timestamp

    def is_next_key(self, region, timestamp):
        """ Check if there is more keys to transmit for a given region in a\
            given timestamp

        :param region: the region ID to check
        :param timestamp: the timestamp to check
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

        :param region: the region ID to check
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
