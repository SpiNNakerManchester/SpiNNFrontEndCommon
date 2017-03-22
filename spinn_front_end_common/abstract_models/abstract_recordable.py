from six import add_metaclass

from spinn_utilities.abstract_base import AbstractBase, abstractmethod


@add_metaclass(AbstractBase)
class AbstractRecordable(object):
    """ Indicates that an object might record some data in to SDRAM
    """
    __slots__ = ()

    @abstractmethod
    def is_recording(self):
        """ Deduce if the recorder is actually recording
        """
