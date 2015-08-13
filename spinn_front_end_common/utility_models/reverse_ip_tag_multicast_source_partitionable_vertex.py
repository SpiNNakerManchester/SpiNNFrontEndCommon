from pacman.model.partitionable_graph.abstract_partitionable_vertex\
    import AbstractPartitionableVertex

from spinn_front_end_common.utilities import simulation_utilities
from spinn_front_end_common.utility_models.reverse_ip_tag_multi_cast_source\
    import ReverseIpTagMultiCastSource
from pacman.model.constraints.key_allocator_constraints\
    .key_allocator_fixed_key_and_mask_constraint \
    import KeyAllocatorFixedKeyAndMaskConstraint
from pacman.model.routing_info.key_and_mask import KeyAndMask


class ReverseIPTagMulticastSourcePartitionableVertex(
        AbstractPartitionableVertex):
    """ Utility vertex to allow a vertex to extend this
    """

    def __init__(self, label, n_keys, virtual_key=None,
                 buffer_space=0, constraints=None):
        AbstractPartitionableVertex(n_keys, label, n_keys, constraints)
        self._virtual_key = virtual_key
        self._buffer_space = buffer_space

    def get_outgoing_edge_constraints(self, partitioned_edge, graph_mapper):
        """
        """
        if self._virtual_key is not None:
            return list([KeyAllocatorFixedKeyAndMaskConstraint(
                [KeyAndMask(self._virtual_key, self._mask)])])
        return list()

    @property
    def model_name(self):
        """
        """
        return "ReverseIpTagMultiCastSource"

    def get_sdram_usage_for_atoms(self, vertex_slice, graph):
        """
        """
        return (simulation_utilities.HEADER_REGION_BYTES +
                ReverseIpTagMultiCastSource._CONFIGURATION_REGION_SIZE +
                self._buffer_space)

    def get_dtcm_usage_for_atoms(self, vertex_slice, graph):
        """
        """
        return ReverseIpTagMultiCastSource._CONFIGURATION_REGION_SIZE

    def get_cpu_usage_for_atoms(self, vertex_slice, graph):
        """
        """
        return 1
