from abc import ABCMeta
from six import add_metaclass
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractProvidesProvenanceDataFromMachine(object):
    """ Indicates that an object provides provenance data retrieved from the\
        machine
    """

    def __init__(self):
        pass

    @abstractmethod
    def get_provenance_data_from_machine(self, transceiver, placement):
        """ Get an iterable of provenance data items

        :param transceiver: the SpinnMan interface object
        :param placement: the placement of the object
        :return: iterable of ProvenanceDataItem
        """
