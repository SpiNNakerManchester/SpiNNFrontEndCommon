from six import add_metaclass
from abc import ABCMeta

from spinn_front_end_common.abstract_models.abstract_starts_synchronized \
    import AbstractStartsSynchronized


@add_metaclass(ABCMeta)
class AbstractBinaryUsesSimulationRun(AbstractStartsSynchronized):
    """ Indicates that the binary run time can be updated
    """
