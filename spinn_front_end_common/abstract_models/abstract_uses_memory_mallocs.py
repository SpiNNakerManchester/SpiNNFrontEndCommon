from abc import ABCMeta
from six import add_metaclass
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractPartitionableUsesMemoryMallocs(object):

    def __init__(self):
        pass

    @abstractmethod
    def get_number_of_mallocs_used_by_dsg(self, vertex_slice, in_edges):
        """
        get the number of mallocs required by the model
        :param in_edges: the number of edges coming into this model
        :param vertex_slice: the slice from a partitionable vertex associated
        with the partitioned_vertex
        :return: the number of mallocs used by this model
        :rtype: int
        """