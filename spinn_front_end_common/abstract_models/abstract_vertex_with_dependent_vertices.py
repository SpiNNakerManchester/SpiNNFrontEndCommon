# general imports
from six import add_metaclass
from abc import ABCMeta, abstractmethod


@add_metaclass(ABCMeta)
class AbstractVertexWithEdgeToDependentVertices(object):
    """ A vertex with a dependent vertices, which should be connected to this\
        vertex by an edge directly to each of them
    """

    @abstractmethod
    def dependent_vertices(self):
        """ Return the vertices which this vertex depends upon
        :return:
        """

    @abstractmethod
    def edge_partition_identifiers_for_dependent_vertex(self, vertex):
        """ Return the dependent edge identifiers for this vertex
        """
