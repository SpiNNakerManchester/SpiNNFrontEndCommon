from six import add_metaclass
from abc import ABCMeta
from abc import abstractproperty


@add_metaclass(ABCMeta)
class AbstractSendMeMulticastCommandsVertex(object):
    """ A vertex which wants to commands to be sent to it as multicast packets
        at fixed points in the simulation
    """

    @abstractproperty
    def start_resume_commands(self):
        """ The commands needed when starting or resuming simulation
        """

    @abstractproperty
    def pause_stop_commands(self):
        """ The commands needed when pausing or stopping simulation
        """

    @abstractproperty
    def timed_commands(self):
        """ The commands to be sent at given times in the simulation
        """
