from six import add_metaclass
from abc import ABCMeta
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractRecordableInterface(object):
    """
    AbstractRecordableInterface: interface to allow FEC to deduce if recording
    aspects are operating correctly.
    """

    @abstractmethod
    def is_recording(self):
        """
        method for deducing if the recorder is actually recording.
        :return:
        """