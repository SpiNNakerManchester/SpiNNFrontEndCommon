from six import add_metaclass

from spinn_utilities.abstract_base import AbstractBase

@add_metaclass(AbstractBase)
class AbstractStartsSynchronized(object):
    """ Indicates that the binary starts in synchronisation with other\
        binaries in the simulation
    """

    __slots__ = ()
