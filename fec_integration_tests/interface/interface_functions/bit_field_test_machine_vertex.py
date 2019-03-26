from enum import Enum

from pacman.executor.injection_decorator import inject_items
from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import ResourceContainer
from spinn_front_end_common.abstract_models import \
    AbstractGeneratesDataSpecification, AbstractProvidesNKeysForPartition
from spinn_front_end_common.abstract_models.\
    abstract_supports_bit_field_routing_compression import \
    AbstractSupportsBitFieldRoutingCompression
from spinn_front_end_common.utilities import helpful_functions
from spinn_utilities.overrides import overrides


class BitFieldTestMachineVertex(
        MachineVertex, AbstractSupportsBitFieldRoutingCompression,
        AbstractGeneratesDataSpecification, AbstractProvidesNKeysForPartition):

    # Regions for populations
    DSG_REGIONS = Enum(
        value="DSG_REGIONS",
        names=[('BIT_FIELD_FILTER', 1),
               ('KEY_ATOM_REGION', 2),
               ('STEAL_REGION_START', 3)])

    def __init__(self, how_many_stealable_regions,
                 size_to_allocate_to_steal, bit_field_region_data):
        MachineVertex.__init__(self, "test_vertex", [])
        AbstractSupportsBitFieldRoutingCompression.__init__(self)
        AbstractGeneratesDataSpecification.__init__(self)

        self._bit_field_region_data = bit_field_region_data
        self._partition_to_n_atoms_map = dict()
        self._steal_able_region_sizes = list()
        self._routing_info = None

        if how_many_stealable_regions != 0:
            each_region = size_to_allocate_to_steal / how_many_stealable_regions
            for _ in range(0, how_many_stealable_regions):
                self._steal_able_region_sizes.append(each_region)

    def set_routing_infos(self, routing_info):
        self._routing_info = routing_info

    def add_n_keys_to_partition(self, partition, n_keys):
        self._partition_to_n_atoms_map[partition] = n_keys

    def get_n_keys_for_partition(self, partition, graph_mapper):
        if partition in self._partition_to_n_atoms_map:
            return self._partition_to_n_atoms_map[partition]
        else:
            return 1

    def _deduce_key_atom_size(self, machine_graph):
        n_incoming_partitions = len(machine_graph.get_edges_ending_at_vertex(
            self))
        return 4 + (n_incoming_partitions * 8)

    def _deduce_bit_field_size(self):
        static = 4 + (len(self._bit_field_region_data) * 8)
        for (_, words) in self._bit_field_region_data:
            static += len(words) * 4
        return static

    @inject_items({"machine_graph": "MemoryMachineGraph"})
    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification,
        additional_arguments={"machine_graph"})
    def generate_data_specification(self, spec, placement, machine_graph):
        spec.reserve_memory_region(
            region=self.DSG_REGIONS.BIT_FIELD_FILTER.value,
            size=self._deduce_bit_field_size(),
            label='bit field')
        spec.reserve_memory_region(
            region=self.DSG_REGIONS.KEY_ATOM_REGION.value,
            size=self._deduce_key_atom_size(machine_graph),
            label='bit field')
        for index, size in enumerate(self._steal_able_region_sizes):
            spec.reserve_memory_region(
                region=self.DSG_REGIONS.STEAL_REGION_START.value + index,
                size=size, shrink=False,
                label='steal region {}'.format(index))

        spec.switch_write_focus(self.DSG_REGIONS.BIT_FIELD_FILTER.value)
        spec.write_value(len(self._bit_field_region_data))
        for (key, words) in self._bit_field_region_data:
            spec.write_value(key)
            spec.write_value(len(words))
            for word in words:
                spec.write(word)

        spec.switch_write_focus(self.DSG_REGIONS.KEY_ATOM_REGION.value)
        spec.write_value(len(machine_graph.get_edges_ending_at_vertex(
            self)))

        # load in key to max atoms map
        for in_coming_edge in machine_graph.get_edges_ending_at_vertex(
                self):
            spec.write_value(self._routing_info.get_first_key_from_partition(
                machine_graph.get_outgoing_partition_for_edge(in_coming_edge)))
            spec.write_value(
                len(self._routing_info.get_routing_info_for_edge(
                    in_coming_edge).get_keys()))
        spec.end_specification()

    @property
    def resources_required(self):
        return ResourceContainer()

    def bit_field_base_address(self, transceiver, placement):
        return helpful_functions.locate_memory_region_for_placement(
            placement=placement, transceiver=transceiver,
            region=self.DSG_REGIONS.BIT_FIELD_FILTER.value)

    def key_to_atom_map_region_base_address(self, transceiver, placement):
        return helpful_functions.locate_memory_region_for_placement(
            placement=placement, transceiver=transceiver,
            region=self.DSG_REGIONS.BIT_FIELD_BUILDER.value)

    def regeneratable_sdram_blocks_and_sizes(self, transceiver, placement):
        result = list()
        for index, size in enumerate(self._steal_able_region_sizes):
            address = helpful_functions.locate_memory_region_for_placement(
                placement=placement, transceiver=transceiver,
                region=self.DSG_REGIONS.STEAL_REGION_START.value + index)
            result.append((address, size))
        return result
