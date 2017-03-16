from six import add_metaclass

from spinn_front_end_common.abstract_models.abstract_starts_synchronized \
    import AbstractStartsSynchronized
from spinn_utilities.abstract_base import AbstractBase, abstractmethod

@add_metaclass(AbstractBase)
class AbstractBinaryUsesSimulationRun(AbstractStartsSynchronized):
    """ Indicates that the binary run time can be updated
    """

    __slots__ = ()
