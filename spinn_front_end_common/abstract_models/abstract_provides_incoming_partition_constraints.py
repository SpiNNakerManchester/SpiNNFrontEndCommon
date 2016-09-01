from six import add_metaclass
from abc import ABCMeta
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractProvidesIncomingPartitionConstraints(object):
    """ A vertex that can provide constraints for its incoming edge partitions
    """

    @abstractmethod
    def get_incoming_partition_constraints(self, partition):
        """ Get constraints to be added to the given edge that goes in to\
            a vertex of this vertex

        :param partition: An partition that goes in to this vertex
        :type partition:\
                    :py:class:`pacman.utilities.utility_objs.outgoing_partition.OutgoingPartition`
        :return: A list of constraints
        :rtype: list of\
                    :py:class:`pacman.model.constraints.abstract_constraint.AbstractConstraint`
        """
