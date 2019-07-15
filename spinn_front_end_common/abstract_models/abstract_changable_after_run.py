from six import add_metaclass
from spinn_utilities.abstract_base import (
    AbstractBase, abstractmethod)


@add_metaclass(AbstractBase)
class AbstractChangableAfterRun(object):
    """ An item that can be changed after a call to run, the changes to which\
        might or might not require mapping or data generation.
    """

    __slots__ = ()

    @property
    def requires_mapping(self):
        """ True if changes that have been made require that mapping be\
            performed.  By default this returns False but can be overridden to\
            indicate changes that require mapping.

        :rtype: bool
        """
        return False

    @property
    def requires_data_generation(self):
        """ True if changes that have been made require that data generation\
            be performed.  By default this returns False but can be overridden\
            to indicate changes that require data regeneration.

        :rtype: bool
        """
        return False

    @abstractmethod
    def mark_no_changes(self):
        """ Marks the point after which changes are reported, so that new\
            changes can be detected before the next check.
        """
