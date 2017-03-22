from six import add_metaclass

from spinn_utilities.abstract_base import AbstractBase, abstractmethod

from pacman.executor.injection_decorator import supports_injection
from pacman.executor.injection_decorator import inject


@supports_injection
@add_metaclass(AbstractBase)
class NeedsNMachineTimeSteps(object):
    """ A class that uses the number of machine time steps
    """

    __slots__ = ()

    @inject("TotalMachineTimeSteps")
    @abstractmethod
    def set_n_machine_time_steps(self, n_machine_time_steps):
        pass
