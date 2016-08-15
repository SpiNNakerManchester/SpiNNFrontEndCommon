from six import add_metaclass
from abc import ABCMeta
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractProvidesOutgoingPartitionConstraints(object):
    """ A vertex that can provide constraints for its outgoing edge partitions
    """

    @abstractmethod
    def get_outgoing_partition_constraints(self, partition):
        """ Get constraints to be added to the given edge that comes out of\
            this vertex

        :param partition: An edge that comes out of this vertex
        :param graph_mapper: A mapper between the graphs
        :type graph_mapper:\
                    :py:class:`pacman.model.graph.graph_mapper.GraphMapper`
        :return: A list of constraints
        :rtype: list of\
                    :py:class:`pacman.model.constraints.abstract_constraint.AbstractConstraint`
        """
        pass
