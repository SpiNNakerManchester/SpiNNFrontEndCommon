from six import add_metaclass

from spinn_utilities.abstract_base import \
    AbstractBase, abstractmethod, abstractproperty


@add_metaclass(AbstractBase)
class AbstractChangableAfterRun(object):
    """ An item that can be changed after a call to run, the changes to which\
        might or might not require mapping
    """

    __slots__ = ()

    @abstractproperty
    def requires_mapping(self):
        """ True if changes that have been made require that mapping be\
            performed.  Note that this should return True the first time it\
            is called, as the vertex must require mapping as it has been\
            created!
        """

    @abstractmethod
    def mark_no_changes(self):
        """ Marks the point after which changes are reported.  Immediately\
            after calling this method, requires_mapping should return False.
        """
