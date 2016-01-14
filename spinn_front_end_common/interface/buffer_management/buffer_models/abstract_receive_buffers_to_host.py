from abc import ABCMeta
from abc import abstractmethod
from six import add_metaclass


@add_metaclass(ABCMeta)
class AbstractReceiveBuffersToHost(object):
    """ Indicates that this object can receive buffers
    """

    @abstractmethod
    def buffering_output(self):
        """ True if the output buffering mechanism is activated

        :return: Boolean indicating whether the output buffering mechanism\
                is activated
        :rtype: bool
        """

    @abstractmethod
    def is_receives_buffers_to_host(self):
        pass
