from six import add_metaclass
from abc import ABCMeta
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractProvidesIncomingEdgeConstraints(object):
    """ A vertex that can provide constraints for its incoming partitioned\
        edges
    """

    @abstractmethod
    def get_incoming_edge_constraints(self, partitioned_edge):
        """ Get constraints to be added to the given edge that goes in to\
            this vertex

        :param partitioned_edge: An edge that goes in to this vertex
        :type partitioned_edge:\
                    :py:class:`pacman.model.partitioned_graph.partitioned_edge.PartitionedEdge`
        :return: A list of constraints
        :rtype: list of\
                    :py:class:`pacman.model.constraints.abstract_constraint.AbstractConstraint`
        """
