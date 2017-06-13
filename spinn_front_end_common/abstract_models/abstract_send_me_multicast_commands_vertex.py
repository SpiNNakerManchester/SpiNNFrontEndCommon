from six import add_metaclass

from spinn_utilities.abstract_base import AbstractBase
from spinn_utilities.abstract_base import abstractproperty


@add_metaclass(AbstractBase)
class AbstractSendMeMulticastCommandsVertex(object):
    """ A vertex which wants to commands to be sent to it as multicast packets
        at fixed points in the simulation
    """

    __slots__ = ()

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
