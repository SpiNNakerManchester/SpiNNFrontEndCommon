from six import add_metaclass
from spinn_utilities.abstract_base import AbstractBase, abstractmethod


@add_metaclass(AbstractBase)
class AbstractRewritesDataSpecification(object):
    """ Indicates an object that allows data to be changed after run,\
        and so can rewrite the data specification
    """

    __slots__ = ()

    @abstractmethod
    def regenerate_data_specification(self, spec, placement):
        """ Regenerate the data specification, only generating regions that\
            have changed and need to be reloaded
        """

    @abstractmethod
    def requires_memory_regions_to_be_reloaded(self):
        """ Return true if any data region needs to be reloaded

        :rtype: bool
        """

    @abstractmethod
    def mark_regions_reloaded(self):
        """ Indicate that the regions have been reloaded
        """
