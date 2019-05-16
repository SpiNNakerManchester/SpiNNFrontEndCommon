from six import add_metaclass
from spinn_utilities.abstract_base import AbstractBase, abstractmethod


@add_metaclass(AbstractBase)
class AbstractReceiveBuffersToHost(object):
    """ Indicates that this object can receive buffers
    """

    __slots__ = ()

    @abstractmethod
    def get_recorded_region_ids(self):
        """ Get the recording region IDs that have been recorded using buffering

        :return: The region numbers that have active recording
        :rtype: iterable(int)
        """

    @abstractmethod
    def get_recording_region_base_address(self, txrx, placement):
        """ Get the recording region base address

        :param txrx: the SpiNNMan instance
        :param placement:\
            the placement object of the core to find the address of
        :return: the base address of the recording region
        """
