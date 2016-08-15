from six import add_metaclass
from abc import ABCMeta
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractRecordable(object):
    """ Indicates that an object might record some data in to SDRAM
    """

    @abstractmethod
    def is_recording(self):
        """ Deduce if the recorder is actually recording
        :return:
        """
