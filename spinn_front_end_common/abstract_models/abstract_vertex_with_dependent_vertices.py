from six import add_metaclass

from spinn_utilities.abstract_base import AbstractBase, abstractmethod


@add_metaclass(AbstractBase)
class AbstractVertexWithEdgeToDependentVertices(object):
    """ A vertex with a dependent vertices, which should be connected to this\
        vertex by an edge directly to each of them
    """

    __slots__ = ()

    @abstractmethod
    def dependent_vertices(self):
        """ Return the vertices which this vertex depends upon
        """

    @abstractmethod
    def edge_partition_identifiers_for_dependent_vertex(self, vertex):
        """ Return the dependent edge identifiers for this vertex
        """
