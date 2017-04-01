from six import add_metaclass

from spinn_utilities.abstract_base import AbstractBase, abstractmethod


@add_metaclass(AbstractBase)
class AbstractProvidesProvenanceDataFromMachine(object):
    """ Indicates that an object provides provenance data retrieved from the\
        machine
    """

    __slots__ = ()

    def __init__(self):
        pass

    @abstractmethod
    def get_provenance_data_from_machine(self, transceiver, placement):
        """ Get an iterable of provenance data items

        :param transceiver: the SpinnMan interface object
        :param placement: the placement of the object
        :return: iterable of ProvenanceDataItem
        """
