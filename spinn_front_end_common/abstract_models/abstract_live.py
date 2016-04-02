from six import add_metaclass
from abc import ABCMeta
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractLive(object):
    """ Indicates an object that sends or receives live during simulation
    """

    @abstractmethod
    def is_active(self):
        """ True if the object is activated
        """
