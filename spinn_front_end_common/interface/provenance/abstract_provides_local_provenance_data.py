from six import add_metaclass
from abc import ABCMeta
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractProvidesLocalProvenanceData(object):
    """ Indicates an object that provides locally obtained provenance data
    """

    @abstractmethod
    def get_local_provenance_data(self):
        """ Get an iterable of provenance data items

        :return: iterable of ProvenanceDataItem
        """
