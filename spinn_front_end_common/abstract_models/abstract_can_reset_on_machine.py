from six import add_metaclass
from spinn_utilities.abstract_base import (
    AbstractBase, abstractmethod)


@add_metaclass(AbstractBase)
class AbstractCanResetOnMachine(object):
    """ Indicates an object that can be reset to time 0 on the machine
    """

    @abstractmethod
    def reset_on_machine(self, txrx):
        """ Reset the object

        :param txrx:\
            A transceiver that can be used to reset data on the machine
        """
