from collections import defaultdict

from fec_integration_tests.base_test_case import BaseTestCase
from fec_integration_tests.interface.interface_functions.\
    bit_field_test_machine_vertex import BitFieldTestMachineVertex
from pacman.model.graphs.machine import MachineEdge
from pacman.model.placements import Placements, Placement
from pacman.model.routing_info import RoutingInfo, PartitionRoutingInfo
from spinn_front_end_common.interface.abstract_spinnaker_base import \
    AbstractSpinnakerBase, CONFIG_FILE
from spinn_front_end_common.utilities.utility_objs import ExecutableFinder
import math
import random


SEED = 4
MAX_CHIPS = 3
USE_RANDOM = True
NEURON_MASK = 0xFFFFFC00


def generate_keys_and_n_atoms(n_chips, vertex_per_chip):
    n_atom_set = [100, 200, 50, 26, 52, 99]
    full_atom_set = dict()
    for chip_id in range(0, n_chips):
        for vertex_id in range(0, vertex_per_chip):
            full_atom_set[(chip_id, vertex_id)] = \
                n_atom_set[vertex_id] * chip_id

    max_key_space = 0
    keys_set = dict()
    for chip_id in range(0, n_chips):
        for vertex_id in range(0, vertex_per_chip):
            n_atoms = full_atom_set[(chip_id, vertex_id)]
            log = math.log(n_atoms, 2)
            log = math.ceil(log)
            keys_set[(chip_id, vertex_id)] = max_key_space
            max_key_space += math.pow(2, log)

    key_atom_map = dict()
    for chip_id in range(0, n_chips):
        for vertex_id in range(0, vertex_per_chip):
            key_atom_map[(chip_id, vertex_id)] = (
                full_atom_set[(chip_id, vertex_id)],
                keys_set[(chip_id, vertex_id)])

    return key_atom_map


def _hand_crafed_bit_field_bits(
        n_chips, vertex_per_chip, default_placements, key_atom_map):
    return []


def generate_bit_fields(
        n_chips, vertex_per_chip, default_placements, key_atom_map):
    bit_fields = defaultdict(list)
    random_words_for_bit_field = list()

    if USE_RANDOM:
        random.seed(SEED)
        for word in range(0, n_chips * vertex_per_chip * 7):
            random_words_for_bit_field.append(random.randint())

        position = 0
        for chip_id in range(0, n_chips):
            for vertex_id in range(0, vertex_per_chip):
                (n_atoms, key) = key_atom_map[(chip_id, vertex_id)]
                n_words = math.ceil(math.log(n_atoms, 2))
                bit_fields[(chip_id, vertex_id)].append(
                    (key,
                     random_words_for_bit_field[position : position+n_words]))
                position += n_words

    else:
        bit_fields = _hand_crafed_bit_field_bits(
            n_chips, vertex_per_chip, default_placements, key_atom_map)
    return bit_fields


def do_run(size_of_chip_left, compressible, time, malloc, overall,
           multiple_chips, n_stealable_regions, stealable_total_size):
    api = AbstractSpinnakerBase(
        configfile=CONFIG_FILE, executable_finder=ExecutableFinder())
    machine = api.machine
    txrx = api.transceiver
    app_id = 16

    # determine how many verts per chip should be compressable or not
    if compressible:
        if multiple_chips:
            verts_per_chip = 2
        else:
            verts_per_chip = 6
    else:
        if multiple_chips:
            verts_per_chip = 3
        else:
            verts_per_chip = 9

    # get chips to work on
    chips = list()
    if multiple_chips:
        n_chips = MAX_CHIPS
    else:
        n_chips = 1

    # get chips
    for chip in machine.chips:
        if len(chips) < n_chips:
            chips.append(chip)

    # get processor ids which will be used for placements
    placement_ids = list()
    for proc in chips[0].processors:
        if not proc.is_monitor:
            placement_ids.append(proc.processor_id)

    # how many chips we're going to run on
    n_chips = 1
    if multiple_chips:
        n_chips = 3

    # create placements
    placements = Placements()

    # create key and bitfields
    key_atom_map = generate_keys_and_n_atoms(n_chips, verts_per_chip)
    bit_fields = generate_bit_fields(
        n_chips, verts_per_chip, placement_ids, key_atom_map)

    # make verts
    verts = list()
    for chip_index, chip in enumerate(chips):
        for vertex_index in range(0, verts_per_chip):
            vertex = BitFieldTestMachineVertex(
                how_many_stealable_regions=n_stealable_regions,
                size_to_allocate_to_steal=stealable_total_size,
                bit_field_region_data=bit_fields[(chip_index, vertex_index)])
            verts.append(vertex)
            placements.add_placement(Placement(
                x=chip.x, y=chip.y, p=placement_ids[vertex_index],
                vertex=vertex))
            api.add_machine_vertex(vertex)

    # make edges
    coverage = [2, 4, 6, 1, 3, 5, 7, 5, 1]
    for index, vertex in enumerate(verts):
        coverage_index = index % len(coverage)
        for edge_index in range(0, coverage[coverage_index]):
            edge = MachineEdge(vertex, verts[index + edge_index])
            api.add_machine_edge(edge, "test")

    # build routing info
    graph = api.machine_graph
    routing_info = RoutingInfo()
    for partition in graph.outgoing_edge_partitions():

        pre_vertex = partition.pre_vertex

        routing_info.add_partition_info(
            PartitionRoutingInfo(keys_and_masks, partition)

    # allocate sdram so that its matching what we want.
    for chip in chips:
        basic_ship_sdram_size = chip.sdram.size
        to_alloc = basic_ship_sdram_size - size_of_chip_left
        if to_alloc > 0:
            txrx.malloc_sdram(chip.x, chip.y, to_alloc, app_id)






class BitFieldRouterCompressorTest(BaseTestCase):

    def run_with_no_compression(self):
        pass

    def run_with_successful_compression(self):
        pass

    def run_with_failed_compression_time(self):
        pass

    def run_with_failed_compression_malloc(self):
        pass

    def run_with_failed_compression_overall_fail(self):
        pass

    def test_with_multiple_chips(self):
        pass

    def run_with_less_memory_than_all_but_compressed(self):
        pass

    def test_runs(self):
        self.runsafe(self.run_with_no_compression)
        self.runsafe(self.run_with_successful_compression)
        self.runsafe(self.run_with_failed_compression_time)
        self.runsafe(self.run_with_failed_compression_malloc)
        self.runsafe(self.run_with_failed_compression_overall_fail)
        self.runsafe(self.test_with_multiple_chips)

if __name__ == '__main__':
    x = BitFieldRouterCompressorTest()
    x.run_with_no_compression()
    x.run_with_successful_compression()
    x.run_with_failed_compression_time()
    x.run_with_failed_compression_malloc()
    x.run_with_failed_compression_overall_fail()
    x.test_with_multiple_chips()
    x.run_with_less_memory_than_all_but_compressed()


