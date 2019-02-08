from six import add_metaclass
from spinn_utilities.abstract_base import AbstractBase, abstractmethod


@add_metaclass(AbstractBase)
class AbstractProvidesKeyToAtomMapping(object):
    """ Interface to provide a mapping between routing key partitions and\
        atom IDs
    """

    __slots__ = ()

    @abstractmethod
    def routing_key_partition_atom_mapping(self, routing_info, partition):
        """ Returns a list of atom to key mapping.

        :param routing_info: the routing info object to consider
        :param partition: the routing partition to handle.
        :return: a iterable of tuples of atom IDs to keys.
        """
