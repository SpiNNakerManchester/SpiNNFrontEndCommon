from six import add_metaclass
from spinn_utilities.abstract_base import AbstractBase, abstractproperty


@add_metaclass(AbstractBase)
class AbstractSupportsDatabaseInjection(object):
    """ Marks a machine vertex as supporting injection of information via a\
        database running on the controlling host.
    """

    __slots__ = ()

    @abstractproperty
    def is_in_injection_mode(self):
        """ Whether this vertex is actually in injection mode.
        """
