from abc import ABCMeta
from six import add_metaclass
from abc import abstractmethod

@add_metaclass(ABCMeta)
class AbstractProvidesProvenanceData(object):
    """
    AbstractProvidesProvenanceData
    """

    def __init__(self):
        pass

    @abstractmethod
    def write_provenance_data_in_xml(self, file_path, transceiver,
                                     placement=None):
        """
        abstract method to force objects extending this to provide a xml
        element object for output
        :param file_path: the file apth to write the provanence data to
        :param transceiver: the spinnman interface object
        :param placement: the placement object for this subvertex or None if
        the system does not require a placement object
        :return: None
        """

