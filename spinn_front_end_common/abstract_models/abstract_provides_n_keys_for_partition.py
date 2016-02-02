from six import add_metaclass
from abc import abstractmethod
from abc import ABCMeta


@add_metaclass(ABCMeta)
class AbstractProvidesNKeysForPartition(object):
    """ Allows a vertex to provide the number of keys for a partition of edges,\
        rather than relying on the number of atoms in the pre-subvertex
    """

    @abstractmethod
    def get_n_keys_for_partition(self, partition, graph_mapper):
        """ Get the number of keys required by the given partition of edges

        :param partition: An partition that comes out of this vertex
        :type partition:\
                    :py:class:`pacman.utilities.utility_objs.outgoing_partition.OutgoingPartition`
        :param graph_mapper: A mapper between the partitioned edges and the \
                    associated partitionable edges
        :type graph_mapper:\
                    :py:class:`pacman.model.graph_mapper.graph_mapper.GraphMapper`
        :return: A list of constraints
        :rtype: list of\
                    :py:class:`pacman.model.constraints.abstract_constraint.AbstractConstraint`
        """
        pass
