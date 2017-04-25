from six import add_metaclass

from spinn_utilities.abstract_base import AbstractBase, abstractmethod


@add_metaclass(AbstractBase)
class AbstractProvidesOutgoingPartitionConstraints(object):
    """ A vertex that can provide constraints for its outgoing edge partitions
    """

    __slots__ = ()

    @abstractmethod
    def get_outgoing_partition_constraints(self, partition):
        """ Get constraints to be added to the given edge that comes out of\
            this vertex

        :param partition: An edge that comes out of this vertex
        :return: A list of constraints
        :rtype: list of\
                    :py:class:`pacman.model.constraints.abstract_constraint.AbstractConstraint`
        """
        pass
