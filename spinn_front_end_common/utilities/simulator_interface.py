from six import add_metaclass

from spinn_utilities.abstract_base import AbstractBase
from spinn_utilities.abstract_base import abstractproperty
# from spinn_utilities.abstract_base import abstractmethod


@add_metaclass(AbstractBase)
class SimulatorInterface(object):

    __slots__ = ()

    @abstractproperty
    def config(self):
        pass
