from six import add_metaclass
from abc import ABCMeta
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractRewritesDataSpecification(object):
    """ Indicates an object that allows data to be changed after run,\
        and so can rewrite the data specification
    """

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
