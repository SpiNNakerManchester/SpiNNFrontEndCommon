# general imports
from six import add_metaclass
from abc import ABCMeta

from spinn_front_end_common.abstract_models.\
    abstract_vertex_with_dependent_vertices import \
    AbstractVertexWithEdgeToDependentVertices


@add_metaclass(ABCMeta)
class VertexWithEdgeToDependentVertices(
        AbstractVertexWithEdgeToDependentVertices):
    """ A vertex with a dependent vertices, which should be connected to this\
        vertex by an edge directly to each of them
    """

    def __init__(self, dependent_vertices_to_edge_partition_identifier):
        """

        :param dependent_vertices_to_edge_partition_identifier:\
                The vertex to edge partition identifiers
        :type dependent_vertices_to_edge_partition_identifier: dict
        :return: None
        :rtype: None
        :raise None: this method does not raise any known exception
        """
        AbstractVertexWithEdgeToDependentVertices.__init__(self)
        self._dependent_vertices_to_edge_partition_identifier = \
            dependent_vertices_to_edge_partition_identifier

    def dependent_vertices(self):
        """ Return the vertices which this vertex depends upon
        """
        return self._dependent_vertices_to_edge_partition_identifier.keys()

    def edge_partition_identifiers_for_dependent_vertex(self, vertex):
        """ Return the dependent edge identifier
        """
        return self._dependent_vertices_to_edge_partition_identifier[vertex]
