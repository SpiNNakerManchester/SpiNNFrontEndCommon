# Copyright (c) 2019 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections import defaultdict
import functools
import math
import os
import struct
from typing import Dict, List, Optional, Tuple, cast
from spinn_utilities.config_holder import get_config_bool
from spinn_utilities.find_max_success import find_max_success
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.ordered_set import OrderedSet
from spinn_machine import MulticastRoutingEntry, Chip
from pacman.exceptions import (
    PacmanAlgorithmFailedToGenerateOutputsException,
    PacmanElementAllocationException, MinimisationFailedError)
from pacman.model.routing_tables import (
    AbstractMulticastRoutingTable, MulticastRoutingTables,
    UnCompressedMulticastRoutingTable, CompressedMulticastRoutingTable)
from pacman.utilities.algorithm_utilities.routes_format import format_route
from pacman.operations.router_compressors import RTEntry
from pacman.operations.router_compressors.pair_compressor import (
    _PairCompressor)
from spinn_front_end_common.abstract_models import (
    AbstractSupportsBitFieldRoutingCompression)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.helpful_functions import n_word_struct
from spinn_front_end_common.utilities.constants import (
    BYTES_PER_WORD, BYTES_PER_4_WORDS)
from spinn_front_end_common.utilities.report_functions.\
    bit_field_compressor_report import (
        generate_provenance_item)

_REPORT_FOLDER_NAME = "router_compressor_with_bitfield"


def host_based_bit_field_router_compressor() -> MulticastRoutingTables:
    """
    Entry point when using the PACMANAlgorithmExecutor.

    :return: compressed routing table entries
    :rtype: ~pacman.model.routing_tables.MulticastRoutingTables
    """
    routing_tables = FecDataView.get_uncompressed().routing_tables
    # create progress bar
    progress = ProgressBar(
        len(routing_tables) * 2,
        "Compressing routing Tables with bitfields in host")

    # create report
    if get_config_bool(
            "Reports", "write_router_compression_with_bitfield_report"):
        report_folder_path = generate_report_path()
    else:
        report_folder_path = None

    # compressed router table
    compressed_pacman_router_tables = MulticastRoutingTables()

    key_atom_map = generate_key_to_atom_map()

    most_costly_cores: Dict[Chip, Dict[int, int]] = defaultdict(
        lambda: defaultdict(int))
    for partition in FecDataView.iterate_partitions():
        for edge in partition.edges:
            splitter = edge.post_vertex.splitter
            for vertex, _ in splitter.get_source_specific_in_coming_vertices(
                    partition.pre_vertex, partition.identifier):
                place = FecDataView.get_placement_of_vertex(vertex)
                most_costly_cores[place.chip][place.p] += 1

    # start the routing table choice conversion
    compressor = HostBasedBitFieldRouterCompressor(
        key_atom_map, report_folder_path, most_costly_cores)
    for router_table in progress.over(routing_tables):
        compressor.compress_bitfields(
            router_table, compressed_pacman_router_tables)

    # return compressed tables
    return compressed_pacman_router_tables


def generate_report_path() -> str:
    """
    :rtype: str
    """
    report_folder_path = os.path.join(
        FecDataView.get_run_dir_path(), _REPORT_FOLDER_NAME)
    if not os.path.exists(report_folder_path):
        os.mkdir(report_folder_path)
    return report_folder_path


def generate_key_to_atom_map() -> Dict[int, int]:
    """
    *THIS IS NEEDED* due to the link from key to edge being lost.

    :return: key to atom map based of key to n atoms
    :rtype: dict(int,int)
    """
    # build key to n atoms map
    routing_infos = FecDataView.get_routing_infos()
    key_to_n_atoms_map: Dict[int, int] = dict()
    for partition in FecDataView.iterate_partitions():
        for vertex in partition.pre_vertex.splitter.get_out_going_vertices(
                partition.identifier):
            key = routing_infos.get_first_key_from_pre_vertex(
                vertex, partition.identifier)
            if key is not None:
                key_to_n_atoms_map[key] = vertex.vertex_slice.n_atoms
    return key_to_n_atoms_map


class _BitFieldData(object):
    __slots__ = (
        # bit_field data
        "bit_field",
        # Key this applies to
        "master_pop_key",
        # address of n_atoms word to wrote back merged flags
        "n_atoms_address",
        # Word that holds merged: 1; all_ones: 1; n_atoms: 30;
        "n_atoms_word",
        # P coordinate of processor this applies to
        "processor_id",
        # index of this entry in the "sorted_list"
        "sort_index",
        # The shift to get the core id
        "core_shift",
        # The number of atoms per core
        "n_atoms_per_core")

    def __init__(self, processor_id: int, bit_field: Tuple[int, ...],
                 master_pop_key: int, n_atoms_address: int, n_atoms_word: int,
                 core_shift: int, n_atoms_per_core: int):
        self.processor_id = processor_id
        self.bit_field = bit_field
        self.master_pop_key = master_pop_key
        self.n_atoms_address = n_atoms_address
        self.n_atoms_word = n_atoms_word
        self.core_shift = core_shift
        self.n_atoms_per_core = n_atoms_per_core
        self.sort_index = 0

    def __str__(self) -> str:
        return f"{self.processor_id} {self.master_pop_key} {self.bit_field}"

    def bit_field_as_bit_array(self) -> List[int]:
        """
        Convert the bitfield into an array of bits like bit_field.c
        """
        return [(word >> i) & 1
                for word in self.bit_field
                for i in range(32)]


class HostBasedBitFieldRouterCompressor(object):
    """
    Host-based fancy router compressor using the bitfield filters of the
    cores. Compresses bitfields and router table entries together as
    much as feasible.
    """

    __slots__ = (
        # List of the entries from the highest successful midpoint
        "_best_routing_entries",
        # The highest successful midpoint
        "_best_midpoint",
        # Dict of lists of the original bitfields by key
        "_bit_fields_by_key",
        # Record of which midpoints where tired and with what result
        "_compression_attempts",
        # Number of bitfields for this core
        "_n_bitfields",
        # Mapping from base keys to size of vertex that they were issued for
        "__key_atom_map",
        # Mapping from chip to processor ID to count of incoming on processor
        "__core_cost_map",
        # Where, if anywhere, reports on compression will be written
        "__report_folder")

    # max entries that can be used by the application code
    _MAX_SUPPORTED_LENGTH = 1023

    # the amount of time each attempt at router compression can be allowed to
    #  take (in seconds)
    # _DEFAULT_TIME_PER_ITERATION = 5 * 60
    _DEFAULT_TIME_PER_ITERATION = 10

    # report name
    _REPORT_NAME = "router_{}_{}.rpt"

    # key id for the initial entry
    _ORIGINAL_ENTRY = 0

    # key id for the bitfield entries
    _ENTRIES = 1

    # size of a filter info in bytes (key, n words, pointer)
    _SIZE_OF_FILTER_INFO_IN_BYTES = 12

    # bit to mask a bit
    _BIT_MASK = 1

    # mask for neuron level
    _NEURON_LEVEL_MASK = 0xFFFFFFFF

    # to remove the first   merged: 1; and all_ones: 1;
    N_ATOMS_MASK = 0x3FFFFFFF
    MERGED_SETTER = 0x80000000

    # struct for performance requirements.
    _FOUR_WORDS = struct.Struct("<IIII")

    # for router report
    _LOWER_16_BITS = 0xFFFF

    # threshold starting point at 1ms time step
    _N_PACKETS_PER_SECOND = 100000

    # convert between milliseconds and second
    _MS_TO_SEC = 1000

    # fraction effect for threshold
    _THRESHOLD_FRACTION_EFFECT = 2

    # Number of bits per word as an int
    _BITS_PER_WORD = 32

    def __init__(self, key_to_n_atom_map: Dict[int, int],
                 report_folder_path: Optional[str],
                 most_costly_cores: Dict[Chip, Dict[int, int]]):
        """
        :param dict(int,int) key_to_n_atom_map: key to atoms map
        :param report_folder_path: the report folder base address
        :type report_folder_path: str or None
        :param dict(Chip,dict(int,int)) most_costly_cores:
            Map of chip to processors to count of incoming on processor
        """
        self._best_routing_entries: List[RTEntry] = []
        self._best_midpoint = -1
        self._bit_fields_by_key: Dict[int, List[_BitFieldData]] = {}
        self._compression_attempts: Dict[int, str] = dict()
        self._n_bitfields: int = 0
        self.__key_atom_map = key_to_n_atom_map
        self.__core_cost_map = most_costly_cores
        self.__report_folder = report_folder_path

    def get_bit_field_sdram_base_addresses(
            self, chip_x: int, chip_y: int) -> Dict[int, int]:
        """
        :param int chip_x:
        :param int chip_y:
        """
        # locate the bitfields in a chip level scope
        base_addresses: Dict[int, int] = dict()
        for placement in FecDataView.iterate_placements_by_xy_and_type(
                (chip_x, chip_y), AbstractSupportsBitFieldRoutingCompression):
            vertex = cast(
                AbstractSupportsBitFieldRoutingCompression, placement.vertex)
            base_addresses[placement.p] = vertex.bit_field_base_address(
                FecDataView.get_placement_of_vertex(placement.vertex))
        return base_addresses

    def compress_bitfields(
            self, router_table: AbstractMulticastRoutingTable,
            compressed_pacman_router_tables: MulticastRoutingTables):
        """
        Entrance method for doing on host compression. Can be used as a
        public method for other compressors.

        :param router_table: the routing table in question to compress
        :type router_table:
            ~pacman.model.routing_tables.UnCompressedMulticastRoutingTable
        :param compressed_pacman_router_tables:
            a data holder for compressed tables
        :type compressed_pacman_router_tables:
            ~pacman.model.routing_tables.MulticastRoutingTables
        """
        # Init the per-attempt data
        self._best_routing_entries = []
        self._best_midpoint = -1
        self._bit_fields_by_key = {}
        self._compression_attempts = {}
        self._n_bitfields = 0
        # Find the processors that have bitfield data and where it is
        bit_field_chip_base_addresses = (
            self.get_bit_field_sdram_base_addresses(
                router_table.x, router_table.y))

        # read in bitfields.
        self._read_in_bit_fields(
            router_table.x, router_table.y, bit_field_chip_base_addresses)

        # execute binary search
        self._start_binary_search(router_table)

        # add final to compressed tables:
        # self._best_routing_table is a list of entries
        best_router_table = CompressedMulticastRoutingTable(
            router_table.x, router_table.y)

        if self._best_routing_entries:
            for entry in self._best_routing_entries:
                best_router_table.add_multicast_routing_entry(
                    entry.to_multicast_routing_entry())

        compressed_pacman_router_tables.add_routing_table(best_router_table)

        # remove bitfields from cores that have been merged into the
        # router table
        self._remove_merged_bitfields_from_cores(
            router_table.x, router_table.y)

        # create report file if required
        if self.__report_folder:
            report_file_path = os.path.join(
                self.__report_folder,
                self._REPORT_NAME.format(router_table.x, router_table.y))
            with open(report_file_path, "w", encoding="utf-8") as report_out:
                self._create_table_report(router_table, report_out)

        generate_provenance_item(
            router_table.x, router_table.y, self._best_midpoint)

    def _convert_bitfields_into_router_table(
            self, router_table: AbstractMulticastRoutingTable,
            mid_point: int) -> UnCompressedMulticastRoutingTable:
        """
        Converts the bitfield into router table entries for compression,
        based off the entry located in the original router table.

        :param router_table: the original routing table
        :type router_table:
            ~pacman.model.routing_tables.UnCompressedMulticastRoutingTable
        :param int mid_point: cut-off for bitfields to use
        :return: routing tables.
        :rtype: ~pacman.model.routing_tables.AbstractMulticastRoutingTable
        """
        new_table = UnCompressedMulticastRoutingTable(
            router_table.x, router_table.y)

        # go through the routing tables and convert when needed
        for original_entry in router_table.multicast_routing_entries:
            base_key = original_entry.routing_entry_key
            if base_key not in self._bit_fields_by_key:
                continue
            n_neurons = self.__key_atom_map[base_key]
            entry_links = original_entry.link_ids
            # Assume all neurons for each processor to be kept
            all_mask = [1] * n_neurons
            core_map = {
                processor_id: all_mask
                for processor_id in original_entry.processor_ids}
            # For those below the midpoint use the bitfield data
            for bf_data in self._bit_fields_by_key[base_key]:
                if bf_data.sort_index < mid_point:
                    core_map[bf_data.processor_id] = (
                        bf_data.bit_field_as_bit_array())
            # Add an Entry for each neuron
            for neuron in range(n_neurons):
                # build new entry for this neuron and add to table
                new_table.add_multicast_routing_entry(MulticastRoutingEntry(
                    routing_entry_key=base_key + neuron,
                    mask=self._NEURON_LEVEL_MASK, link_ids=entry_links,
                    defaultable=False, processor_ids=(
                        processor_id
                        for processor_id in original_entry.processor_ids
                        if core_map[processor_id][neuron])))

        # return the bitfield tables and the reduced original table
        return new_table

    def _bit_for_neuron_id(self, bit_field: List[int], neuron_id: int) -> int:
        """
        Locate the bit for the neuron in the bitfield.

        :param list(int) bit_field:
            the block of words which represent the bitfield
        :param int neuron_id: the neuron id to find the bit in the bitfield
        :return: the bit
        """
        word_id, bit_in_word = divmod(neuron_id, self._BITS_PER_WORD)
        return (bit_field[word_id] >> bit_in_word) & self._BIT_MASK

    def _read_in_bit_fields(
            self, chip_x: int, chip_y: int,
            chip_base_addresses: Dict[int, int]):
        """
        Read in the bitfields from the cores.

        :param int chip_x: chip x coordinate
        :param int chip_y: chip y coordinate
        :param dict(int,int) chip_base_addresses:
            maps core id to base address of its bitfields
        """
        self._bit_fields_by_key = defaultdict(list)
        bit_fields_by_coverage = defaultdict(list)
        processor_coverage_by_bitfield = defaultdict(list)

        # read in for each app vertex that would have a bitfield
        for processor_id, base_address in chip_base_addresses.items():
            # from filter_region_t read how many bitfields there are
            # n_filters then array of filters
            n_filters = FecDataView.get_transceiver().read_word(
                chip_x, chip_y, base_address)
            reading_address = base_address + BYTES_PER_WORD

            # read in each bitfield
            for _ in range(n_filters):
                master_pop_key, n_atoms_word, n_per_core_word, read_pointer = \
                    self._FOUR_WORDS.unpack(FecDataView.read_memory(
                        chip_x, chip_y, reading_address, BYTES_PER_4_WORDS))
                n_atoms_address = reading_address + BYTES_PER_WORD
                reading_address += BYTES_PER_4_WORDS

                # merged: 1; all_ones: 1; n_atoms: 30;
                atoms = n_atoms_word & self.N_ATOMS_MASK
                # get bitfield words
                n_words_to_read = math.ceil(atoms / self._BITS_PER_WORD)

                bit_field = n_word_struct(n_words_to_read).unpack(
                    FecDataView.read_memory(
                        chip_x, chip_y, read_pointer,
                        n_words_to_read * BYTES_PER_WORD))

                # sorted by best coverage of redundant packets
                data = _BitFieldData(
                    processor_id, bit_field, master_pop_key, n_atoms_address,
                    n_atoms_word, n_per_core_word & 0x1F, n_per_core_word >> 5)
                as_array = data.bit_field_as_bit_array()
                # Number of fields in the array that are zero instead of one
                n_redundant_packets = len(as_array) - sum(as_array)

                bit_fields_by_coverage[n_redundant_packets].append(data)
                processor_coverage_by_bitfield[processor_id].append(
                    n_redundant_packets)

                # add to the bitfields tracker
                self._bit_fields_by_key[master_pop_key].append(data)

        # use the ordered process to find the best ones to do first
        self._order_bit_fields(
            bit_fields_by_coverage,
            FecDataView.get_chip_at(chip_x, chip_y),
            processor_coverage_by_bitfield)

    def _order_bit_fields(
            self, bit_fields_by_coverage: Dict[int, List[_BitFieldData]],
            chip: Chip, processor_coverage_by_bitfield: Dict[int, List[int]]):
        """
        Order the bit fields by redundancy setting the sorted index.

        Also counts the bitfields setting _n_bitfields.

        :param dict(int,list(_BitFieldData)) bit_fields_by_coverage:
        :param Chip chip:
        :param dict(int,list(int)) processor_coverage_by_bitfield:
        """
        sort_index = 0

        # get cores that are the most likely to have the worst time and order
        #  bitfields accordingly
        cores = sorted(
            self.__core_cost_map[chip].keys(),
            key=lambda k: self.__core_cost_map[chip][k],
            reverse=True)

        # only add bit fields from the worst affected cores, which will
        # build as more and more are taken to make the worst a collection
        # instead of a individual
        cores_to_add_for: OrderedSet[int] = OrderedSet()
        for worst_core_idx in range(len(cores) - 1):
            worst_core = cores[worst_core_idx]
            # determine how many of the worst to add before it balances with
            # next one
            cores_to_add_for.add(worst_core)
            diff = (
                self.__core_cost_map[chip][worst_core] -
                self.__core_cost_map[chip][cores[worst_core_idx + 1]])

            # order over most effective bitfields
            coverage = processor_coverage_by_bitfield[worst_core]
            coverage.sort(reverse=True)

            # cycle till at least the diff is covered
            covered = 0
            for redundant_count in coverage:
                to_delete: List[_BitFieldData] = list()
                for bit_field_data in bit_fields_by_coverage[redundant_count]:
                    if bit_field_data.processor_id in cores_to_add_for:
                        if covered < diff:
                            bit_field_data.sort_index = sort_index
                            sort_index += 1
                            to_delete.append(bit_field_data)
                            covered += 1
                for item in to_delete:
                    bit_fields_by_coverage[redundant_count].remove(item)

        # take left overs
        for coverage_level in sorted(
                bit_fields_by_coverage.keys(), reverse=True):
            for bit_field_data in bit_fields_by_coverage[coverage_level]:
                bit_field_data.sort_index = sort_index
                sort_index += 1

        self._n_bitfields = sort_index

    def _start_binary_search(
            self, router_table: AbstractMulticastRoutingTable):
        """
        Start binary search of the merging of bitfield to router table.

        :param ~.UnCompressedMulticastRoutingTable router_table:
            uncompressed router table
        """
        # try first just uncompressed. so see if its possible
        try:
            self._best_routing_entries = self._run_algorithm(router_table)
            self._best_midpoint = 0
            self._compression_attempts[0] = "success"
        except MinimisationFailedError as e:
            raise PacmanAlgorithmFailedToGenerateOutputsException(
                "host bitfield router compressor can't compress the "
                "uncompressed routing tables, regardless of bitfield merging. "
                "System is fundamentally flawed here") from e

        find_max_success(self._n_bitfields, functools.partial(
            self._binary_search_check, routing_table=router_table))

    def _binary_search_check(
            self, mid_point: int,
            routing_table: AbstractMulticastRoutingTable) -> bool:
        """
        Check function for fix max success.

        :param int mid_point: the point if the list to stop at
        :param ~.UnCompressedMulticastRoutingTable routing_table:
            the basic routing table
        :return: true if it compresses
        :rtype: bool
        """
        # convert bitfields into router tables
        bit_field_router_table = self._convert_bitfields_into_router_table(
            routing_table, mid_point)

        # try to compress
        try:
            self._best_routing_entries = self._run_algorithm(
                bit_field_router_table)
            self._best_midpoint = mid_point
            self._compression_attempts[mid_point] = "success"
            return True
        except MinimisationFailedError:
            self._compression_attempts[mid_point] = "fail"
            return False
        except PacmanElementAllocationException:
            self._compression_attempts[mid_point] = "Exception"
            return False

    def _run_algorithm(
            self, router_table: AbstractMulticastRoutingTable
            ) -> List[RTEntry]:
        """
        Attempts to covert the mega router tables into 1 router table.

        :param list(~.AbstractMulticastRoutingTable) router_table:
            the set of router tables that together need to
            be merged into 1 router table
        :return: compressor router table
        :rtype: list(~.RoutingTableEntry)
        :throws MinimisationFailedError: if it fails to
            compress to the correct length.
        """
        compressor = _PairCompressor(ordered=True)
        compressed_entries = compressor.compress_table(router_table)
        chip = FecDataView.get_chip_at(router_table.x, router_table.y)
        if len(compressed_entries) > chip.n_placable_processors:
            raise MinimisationFailedError(
                f"Compression failed as {len(compressed_entries)} "
                f"entries found")
        return compressed_entries

    def _remove_merged_bitfields_from_cores(self, chip_x: int, chip_y: int):
        """
        Goes to SDRAM and removes said merged entries from the cores'
        bitfield region.

        :param int chip_x: the chip x coordinate from which this happened
        :param int chip_y: the chip y coordinate from which this happened
        """
        assert self._bit_fields_by_key is not None
        for entries in self._bit_fields_by_key.values():
            for entry in entries:
                if entry.sort_index < self._best_midpoint:
                    # set merged
                    n_atoms_word = entry.n_atoms_word | self.MERGED_SETTER
                    FecDataView.write_memory(
                        chip_x, chip_y, entry.n_atoms_address, n_atoms_word)

    def _create_table_report(
            self, router_table: AbstractMulticastRoutingTable, report_out):
        """
        Create the report entry.

        :param ~.AbstractMulticastRoutingTable router_table:
            the uncompressed router table to process
        :param ~io.TextIOBase report_out: the report writer
        """
        n_bit_fields_merged = 0
        n_packets_filtered = 0
        n_possible_bit_fields = 0
        merged_by_core = defaultdict(list)

        for key in self._bit_fields_by_key:
            for bf_data in self._bit_fields_by_key[key]:
                n_possible_bit_fields += 1
                if bf_data.sort_index >= self._best_midpoint:
                    continue
                n_bit_fields_merged += 1
                as_array = bf_data.bit_field_as_bit_array()
                n_packets_filtered += sum(as_array)
                merged_by_core[bf_data.processor_id].append(bf_data)

        percentage_done = 100.0
        if n_possible_bit_fields != 0:
            percentage_done = (
                (100.0 / n_possible_bit_fields) * n_bit_fields_merged)

        report_out.write(
            f"\nTable {router_table.x}:{router_table.y} has integrated "
            f"{n_bit_fields_merged} out of {n_possible_bit_fields} available "
            "chip level bitfields into the routing table, thereby producing a "
            f"compression of {percentage_done}%.\n\n")

        report_out.write(
            "The uncompressed routing table had "
            f"{router_table.number_of_entries} entries, the compressed "
            f"one with {n_bit_fields_merged} integrated bitfields has "
            f"{len(self._best_routing_entries)} entries.\n\n")

        report_out.write(
            f"The integration of {n_bit_fields_merged} bitfields removes up "
            f"to {n_packets_filtered} MC packets that otherwise would be "
            "being processed by the cores on the chip, just to be dropped as "
            "they do not target anything.\n\n")

        report_out.write("The compression attempts are as follows:\n\n")
        for mid_point, result in self._compression_attempts.items():
            report_out.write(f"Midpoint {mid_point}: {result}\n")

        report_out.write("\nThe bit_fields merged are as follows:\n\n")

        for core in merged_by_core:
            for bf_data in merged_by_core[core]:
                report_out.write(
                    f"bitfield on core {core} for "
                    f"key {bf_data.master_pop_key}\n")

        report_out.write("\n\n\n")
        report_out.write("The final routing table entries are as follows:\n\n")

        report_out.write(
            f'{"Index": <5s} {"Key": <10s} {"Mask": <10s} {"Route": <10s} '
            f'#{"Default": <7s} [Cores][Links]\n')
        report_out.write(
            f"{'':-<5s} {'':-<10s} {'':-<10s} {'':-<10s} "
            f"{'':-<7s} {'':-<14s}\n")

        entry_count = 0
        n_defaultable = 0
        # Note: _best_routing_table is a list(), router_table is not
        for entry in self._best_routing_entries:
            index = entry_count & self._LOWER_16_BITS
            entry_str = format_route(entry.to_multicast_routing_entry())
            entry_count += 1
            if entry.defaultable:
                n_defaultable += 1
            report_out.write(f"{index:>5d} {entry_str}\n")
        report_out.write(f"{n_defaultable} Defaultable entries\n")
