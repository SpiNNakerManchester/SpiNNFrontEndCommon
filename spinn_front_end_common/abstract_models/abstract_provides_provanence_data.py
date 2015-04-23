from abc import ABCMeta
from six import add_metaclass
from abc import abstractmethod

@add_metaclass(ABCMeta)
class AbstractProvidesProvanenceData(object):
    """
    AbstractProvidesProvanenceData
    """

    def __init__(self):
        pass

    @abstractmethod
    def _write_provanence_data_in_xml(self, file_path):
        """
        abstract method to force objects extending this to provide a xml
        element object for output
        :param file_path: the file apth to write the provanence data to
        :return: None
        """

