from six import add_metaclass
from abc import ABCMeta, abstractmethod


@add_metaclass(ABCMeta)
class AbstractSendMeMulticastCommandsVertex(object):
    """ A vertex which wants to commands to be sent to it as multicast packets
        at fixed points in the simulation
    """

    @property
    @abstractmethod
    def start_resume_commands(self):
        """
        property method for getting the commands needed during
        start / resume modes
        :return:
        """

    @property
    @abstractmethod
    def pause_stop_commands(self):
        """
        property method for getting the commands needed during
        pause / stop modes
        :return:
        """

    @property
    @abstractmethod
    def timed_commands(self):
        """property method for getting the commands which have to be sent
        at arbitrary times
        :return:
        """
