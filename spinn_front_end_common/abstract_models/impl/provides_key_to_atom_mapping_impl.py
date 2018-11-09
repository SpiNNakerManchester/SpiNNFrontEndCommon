from spinn_utilities.overrides import overrides
from pacman.executor.injection_decorator import inject_items
from spinn_front_end_common.abstract_models import (
    AbstractProvidesKeyToAtomMapping)


class ProvidesKeyToAtomMappingImpl(AbstractProvidesKeyToAtomMapping):
    __slots__ = ()

    @inject_items({
        "graph_mapper": "MemoryGraphMapper"
    })
    @overrides(
        AbstractProvidesKeyToAtomMapping.routing_key_partition_atom_mapping,
        additional_arguments={"graph_mapper"})
    def routing_key_partition_atom_mapping(
            self, routing_info, partition, graph_mapper):
        # pylint: disable=arguments-differ
        vertex_slice = graph_mapper.get_slice(partition.pre_vertex)
        keys = routing_info.get_keys(vertex_slice.n_atoms)
        return list(enumerate(keys, vertex_slice.lo_atom))
