from pacman.model.partitionable_graph.abstract_partitionable_vertex import \
    AbstractPartitionableVertex
from spinn_front_end_common.utility_models\
    .provides_provenance_partitioned_vertex import \
    ProvidesProvenancePartitionedVertex

from abc import ABCMeta
from six import add_metaclass


@add_metaclass(ABCMeta)
class AbstractProvidesProvenancePartitionableVertex(
        AbstractPartitionableVertex):
    """
    AbstractProvidesProvenancePartitionableVertex helper vertex to grab basic
    provenance info from the vertex
    """

    def __init__(
            self, n_atoms, label, max_atoms_per_core, provenance_region_id,
            constraints=None):
        AbstractPartitionableVertex.__init__(
            self, n_atoms, label, max_atoms_per_core, constraints)

        # store region for the partitioned vertex
        self._provenance_region_id = provenance_region_id

    def create_subvertex(
            self, vertex_slice, resources_required, label=None,
            constraints=None):
        """
        @ implements pacman.model.partitionable_graph.partitionable_vertex.PartitionableVertex.create_subvertex
        """
        return ProvidesProvenancePartitionedVertex(
            resources_required, label, constraints, self._provenance_region_id)


