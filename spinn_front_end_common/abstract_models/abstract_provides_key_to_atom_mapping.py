from six import add_metaclass
from abc import ABCMeta
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractProvidesKeyToAtomMapping(object):
    """ interface to provide a mapping between routing key partitions and
    atom ids

    """

    @abstractmethod
    def routing_key_partition_atom_mapping(self, routing_info, partition):
        """ returns a list of atom to key mapping.

        :param routing_info: the routing info object to consider
        :param partition: the routing partition to handle.
        :return: a iterable of tuples of incrementing atom ids to keys.
        """