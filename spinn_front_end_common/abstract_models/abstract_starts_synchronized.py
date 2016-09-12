from six import add_metaclass
from abc import ABCMeta


@add_metaclass(ABCMeta)
class AbstractStartsSynchronized(object):
    """ Indicates that the binary starts in synchronisation with other\
        binaries in the simulation
    """
