# Copyright (c) 2019-2020 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import functools
import math
import os
import struct
from collections import defaultdict
from spinn_utilities.find_max_success import find_max_success
from spinn_utilities.progress_bar import ProgressBar
from spinn_machine import MulticastRoutingEntry
from pacman.exceptions import (
    PacmanAlgorithmFailedToGenerateOutputsException,
    PacmanElementAllocationException, MinimisationFailedError)
from pacman.model.routing_tables import (
    MulticastRoutingTables, UnCompressedMulticastRoutingTable,
    CompressedMulticastRoutingTable)
from pacman.operations.algorithm_reports.reports import format_route
from pacman.operations.router_compressors import Entry
from pacman.operations.router_compressors.ordered_covering_router_compressor\
    import (
        minimise)
from spinn_front_end_common.abstract_models import (
    AbstractSupportsBitFieldRoutingCompression)
from spinn_front_end_common.utilities.helpful_functions import n_word_struct
from spinn_front_end_common.utilities.constants import (
    BYTES_PER_WORD, BYTES_PER_3_WORDS)
from spinn_front_end_common.utilities.report_functions.\
    bit_field_compressor_report import (
        generate_provenance_item)
from pacman.operations.router_compressors import PairCompressor


class _BitFieldData(object):

    __slots__ = [
        # bit_field data
        "bit_field",
        # Key this applies to
        "master_pop_key",
        # address of n_atoms word to wrote back merged flags
        "n_atoms_address",
        # Word that holds merged: 1; all_ones: 1; n_atoms: 30;
        "n_atoms_word",
        # P cooridnate of processor this applies to
        "processor_id",
        # index of this entry in the "sorted_list"
        "sort_index"
    ]

    def __init__(self, processor_id, bit_field, master_pop_key,
                 n_atoms_address, n_atoms_word):
        self.processor_id = processor_id
        self.bit_field = bit_field
        self.master_pop_key = master_pop_key
        self.n_atoms_address = n_atoms_address
        self.n_atoms_word = n_atoms_word
        self.sort_index = None

    def __str__(self):
        return "{} {} {}".format(
            self.processor_id, self.master_pop_key, self.bit_field)

    def bit_field_as_bit_array(self):
        """
        Convert the bitfield into an array of bits like bit_field.c
        """
        return [(word >> i) & 1
                for word in self.bit_field
                for i in range(32)]


class HostBasedBitFieldRouterCompressor(object):
    """ Host-based fancy router compressor using the bitfield filters of the \
        cores. Compresses bitfields and router table entries together as \
        much as feasible.
    """

    __slots__ = [
        # List of the entries from the highest successful midpoint
        "_best_routing_entries",
        # The highest successful midpoint
        "_best_midpoint",
        # Dict of lists of the original bitfields by key
        "_bit_fields_by_key",
        # Record of which midpoints where tired and with what result
        "_compression_attempts",
        # Number of bitfields for this core
        "_n_bitfields"
    ]

    # max entries that can be used by the application code
    _MAX_SUPPORTED_LENGTH = 1023

    # the amount of time each attempt at router compression can be allowed to
    #  take (in seconds)
    # _DEFAULT_TIME_PER_ITERATION = 5 * 60
    _DEFAULT_TIME_PER_ITERATION = 10

    # report name
    _REPORT_FOLDER_NAME = "router_compressor_with_bitfield"
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
    _THREE_WORDS = struct.Struct("<III")

    # for router report
    _LOWER_16_BITS = 0xFFFF

    # rob paul to pay sam threshold starting point at 1ms time step
    _N_PACKETS_PER_SECOND = 100000

    # convert between milliseconds and second
    _MS_TO_SEC = 1000

    # fraction effect for threshold
    _THRESHOLD_FRACTION_EFFECT = 2

    # Number of bits per word as an int
    _BITS_PER_WORD = 32

    def __init__(self):
        self._best_routing_entries = None
        self._best_midpoint = -1
        self._bit_fields_by_key = None
        self._compression_attempts = None

    def __call__(
            self, router_tables, machine, placements, transceiver,
            default_report_folder, produce_report, machine_graph,
            routing_infos,  machine_time_step, time_scale_factor,
            target_length=None):
        """
        Entry point when using the PACMANAlgorithmExecutor

        :param router_tables: routing tables (uncompressed and unordered)
        :type router_tables:
            ~pacman.model.routing_tables.MulticastRoutingTables
        :param ~spinn_machine.Machine machine: SpiNNMachine instance
        :param ~pacman.model.placements.Placements placements: placements
        :param ~spinnman.transceiver.Transceiver transceiver: SpiNNMan instance
        :param str default_report_folder: report folder
        :param bool produce_report: flag for producing report
        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
            the machine graph level
        :param ~pacman.model.routing_info.RoutingInfo routing_infos:
            routing information
        :param int machine_time_step: time step
        :param int time_scale_factor: time scale factor
        :param target_length: length of table entries to get to.
        :type target_length: int or None
        :return: compressed routing table entries
        :rtype: ~pacman.model.routing_tables.MulticastRoutingTables
        """
        if target_length is None:
            target_length = self._MAX_SUPPORTED_LENGTH

        # create progress bar
        progress = ProgressBar(
            len(router_tables.routing_tables) * 2,
            "Compressing routing Tables with bitfields in host")

        # create report
        report_folder_path = None
        if produce_report:
            report_folder_path = self.generate_report_path(
                default_report_folder)

        # compressed router table
        compressed_pacman_router_tables = MulticastRoutingTables()

        key_atom_map = self.generate_key_to_atom_map(
            machine_graph, routing_infos)

        prov_items = list()

        # start the routing table choice conversion
        for router_table in progress.over(router_tables.routing_tables):
            prov_items.append(self.start_compression_selection_process(
                router_table, produce_report, report_folder_path,
                transceiver, machine_graph, placements, machine, target_length,
                compressed_pacman_router_tables, key_atom_map))

        # return compressed tables
        return compressed_pacman_router_tables, prov_items

    def get_bit_field_sdram_base_addresses(
            self, chip_x, chip_y, machine, placements, transceiver):
        """
        :param int chip_x:
        :param int chip_y:
        :param ~spinn_machine.Machine machine:
        :param ~pacman.model.placements.Placements placements:
        :param ~spinnman.transceiver.Transceiver transceiver:
        """
        # locate the bitfields in a chip level scope
        base_addresses = dict()
        n_processors_on_chip = machine.get_chip_at(chip_x, chip_y).n_processors
        for p in range(0, n_processors_on_chip):
            if placements.is_processor_occupied(chip_x, chip_y, p):
                vertex = placements.get_vertex_on_processor(chip_x, chip_y, p)

                if isinstance(
                        vertex, AbstractSupportsBitFieldRoutingCompression):
                    base_addresses[p] = vertex.bit_field_base_address(
                        transceiver, placements.get_placement_of_vertex(
                            vertex))
        return base_addresses

    @staticmethod
    def generate_key_to_atom_map(machine_graph, routing_infos):
        """ THIS IS NEEDED due to the link from key to edge being lost.

        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
            machine graph
        :param ~pacman.model.routing_info.RoutingInfo routing_infos:
            routing infos
        :return: key to atom map based of key to n atoms
        :rtype: dict(int,int)
        """
        # build key to n atoms map
        key_to_n_atoms_map = dict()
        for vertex in machine_graph.vertices:
            for partition in machine_graph.\
                    get_multicast_edge_partitions_starting_at_vertex(vertex):
                key = routing_infos.get_first_key_from_pre_vertex(
                    vertex, partition.identifier)

                key_to_n_atoms_map[key] = (
                    vertex.get_n_keys_for_partition(partition))
        return key_to_n_atoms_map

    def generate_report_path(self, default_report_folder):
        """
        :param str default_report_folder:
        :rtype: str
        """
        report_folder_path = os.path.join(
            default_report_folder, self._REPORT_FOLDER_NAME)
        if not os.path.exists(report_folder_path):
            os.mkdir(report_folder_path)
        return report_folder_path

    def start_compression_selection_process(
            self, router_table, produce_report, report_folder_path,
            transceiver, machine_graph, placements, machine, target_length,
            compressed_pacman_router_tables, key_atom_map):
        """ Entrance method for doing on host compression. Can be used as a \
            public method for other compressors.

        :param router_table: the routing table in question to compress
        :type router_table:
            ~pacman.model.routing_tables.UnCompressedMulticastRoutingTable
        :param bool produce_report: whether the report should be generated
        :param str report_folder_path: the report folder base address
        :param ~spinnman.transceiver.Transceiver transceiver:
            spinnMan instance
        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
            machine graph
        :param ~pacman.model.placements.Placements placements: placements
        :param ~spinn_machine.Machine machine: SpiNNMan instance
        :param int target_length: length of router compressor to get to
        :param compressed_pacman_router_tables:
            a data holder for compressed tables
        :type compressed_pacman_router_tables:
            ~pacman.model.routing_tables.MulticastRoutingTables
        :param dict(int,int) key_atom_map: key to atoms map
            should be allowed to handle per time step
        """
        # Reset all the self values as they change for each routing table
        self._best_routing_entries = None
        self._best_midpoint = -1
        self._bit_fields_by_key = None
        self._compression_attempts = dict()

        # Find the processors that have bitfield data and where it is
        bit_field_chip_base_addresses = (
            self.get_bit_field_sdram_base_addresses(
                router_table.x, router_table.y, machine, placements,
                transceiver))

        # read in bitfields.
        self._read_in_bit_fields(
            transceiver, router_table.x, router_table.y,
            bit_field_chip_base_addresses, machine_graph,
            placements, machine.get_chip_at(
                router_table.x, router_table.y).n_processors)

        # execute binary search
        self._start_binary_search(
            router_table, target_length, key_atom_map)

        # add final to compressed tables:
        # self._best_routing_table is a list of entries
        best_router_table = CompressedMulticastRoutingTable(
            router_table.x, router_table.y)

        for entry in self._best_routing_entries:
            best_router_table.add_multicast_routing_entry(
                entry.to_MulticastRoutingEntry())

        compressed_pacman_router_tables.add_routing_table(best_router_table)

        # remove bitfields from cores that have been merged into the
        # router table
        self._remove_merged_bitfields_from_cores(
            router_table.x, router_table.y, transceiver)

        # create report file if required
        if produce_report:
            report_file_path = os.path.join(
                report_folder_path,
                self._REPORT_NAME.format(router_table.x, router_table.y))
            with open(report_file_path, "w") as report_out:
                self._create_table_report(router_table, report_out)

        return generate_provenance_item(
            router_table.x, router_table.y, self._best_midpoint)

    def _convert_bitfields_into_router_table(
            self, router_table, mid_point, key_to_n_atoms_map):
        """ Converts the bitfield into router table entries for compression, \
            based off the entry located in the original router table.

        :param ~.UnCompressedMulticastRoutingTable router_table:
            the original routing table
        :param int mid_point: cutoff for botfields to use
        :param dict(int,int) key_to_n_atoms_map:
        :return: routing tables.
        :rtype: ~.AbsractMulticastRoutingTable
        """
        new_table = UnCompressedMulticastRoutingTable(
            router_table.x, router_table.y)

        # go through the bitfields and get the routing table for it
        for base_key in self._bit_fields_by_key.keys():
            n_neurons = key_to_n_atoms_map[base_key]
            core_map = dict()
            original_entry = (
                router_table.get_entry_by_routing_entry_key(base_key))
            entry_links = original_entry.link_ids
            # Assume all neurons for each processor to be kept
            for processor_id in original_entry.processor_ids:
                core_map[processor_id] = [1] * n_neurons
            # For those below the midpoint use the bitfield data
            for bf_data in self._bit_fields_by_key[base_key]:
                if bf_data.sort_index < mid_point:
                    core_map[bf_data.processor_id] = (
                        bf_data.bit_field_as_bit_array())
            # Add an Entry for each neuron
            for neuron in range(0, n_neurons):
                processors = list()
                for processor_id in original_entry.processor_ids:
                    if core_map[processor_id][neuron]:
                        processors.append(processor_id)
                # build new entry for this neuron and add to table
                new_table.add_multicast_routing_entry(MulticastRoutingEntry(
                    routing_entry_key=base_key + neuron,
                    mask=self._NEURON_LEVEL_MASK, link_ids=entry_links,
                    defaultable=False, processor_ids=processors))

        # return the bitfield tables and the reduced original table
        return new_table

    def _bit_for_neuron_id(self, bit_field, neuron_id):
        """ locate the bit for the neuron in the bitfield

        :param list(int) bit_field:
            the block of words which represent the bitfield
        :param int neuron_id: the neuron id to find the bit in the bitfield
        :return: the bit
        """
        word_id = int(neuron_id // self._BITS_PER_WORD)
        bit_in_word = neuron_id % self._BITS_PER_WORD
        flag = (bit_field[word_id] >> bit_in_word) & self._BIT_MASK
        return flag

    def _read_in_bit_fields(
            self, transceiver, chip_x, chip_y, bit_field_chip_base_addresses,
            machine_graph, placements, n_processors_on_chip):
        """ reads in the bitfields from the cores

        :param ~.Transceiver transceiver: SpiNNMan instance
        :param int chip_x: chip x coord
        :param int chip_y: chip y coord
        :param ~.MachineGraph machine_graph: machine graph
        :param ~.Placements placements: the placements
        :param int n_processors_on_chip: the number of processors on this chip
        :param dict(int,int) bit_field_chip_base_addresses:
            maps core id to base address
        :return: dict of lists of processor id to bitfields.
        :rtype: tuple(dict(int,list(_BitFieldData)), list(_BitFieldData))
        """

        # data holder
        self._bit_fields_by_key = defaultdict(list)
        bit_fields_by_coverage = defaultdict(list)
        processor_coverage_by_bitfield = defaultdict(list)

        # read in for each app vertex that would have a bitfield
        for processor_id in bit_field_chip_base_addresses.keys():
            bit_field_base_address = (
                bit_field_chip_base_addresses[processor_id])

            # from filter_region_t read how many bitfields there are
            # n_filters then array of filters
            n_filters = transceiver.read_word(
                chip_x, chip_y, bit_field_base_address, BYTES_PER_WORD)
            reading_address = bit_field_base_address + BYTES_PER_WORD

            # read in each bitfield
            for _ in range(0, n_filters):
                # master pop key, n words and read pointer
                master_pop_key, n_atoms_word, read_pointer = \
                    self._THREE_WORDS.unpack(transceiver.read_memory(
                        chip_x, chip_y, reading_address, BYTES_PER_3_WORDS))
                n_atoms_address = reading_address + BYTES_PER_WORD
                reading_address += BYTES_PER_3_WORDS

                # merged: 1; all_ones: 1; n_atoms: 30;
                atoms = n_atoms_word & self.N_ATOMS_MASK
                # get bitfield words
                n_words_to_read = math.ceil(atoms / self._BITS_PER_WORD)

                bit_field = n_word_struct(n_words_to_read).unpack(
                    transceiver.read_memory(
                        chip_x, chip_y, read_pointer,
                        n_words_to_read * BYTES_PER_WORD))

                # sorted by best coverage of redundant packets
                data = _BitFieldData(processor_id, bit_field, master_pop_key,
                                     n_atoms_address, n_atoms_word)
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
            bit_fields_by_coverage, machine_graph, chip_x, chip_y, placements,
            n_processors_on_chip, processor_coverage_by_bitfield)

    def _order_bit_fields(
            self, bit_fields_by_coverage, machine_graph, chip_x, chip_y,
            placements, n_processors_on_chip, processor_coverage_by_bitfield):
        """
        Orders the bit fields by redundancy setting the sorted index

        Also counts the bitfields setting _n_bitfields

        :param dict(int,list(_BitFieldData)) bit_fields_by_coverage:
        :param ~.MachineGraph machine_graph:
        :param int chip_x:
        :param int chip_y:
        :param ~.Placements placements:
        :param int n_processors_on_chip:
        :param dict(int,list(int)) processor_coverage_by_bitfield:
        """
        sort_index = 0

        # get incoming bandwidth for the cores
        most_costly_cores = dict()
        for processor_id in range(0, n_processors_on_chip):
            if placements.is_processor_occupied(chip_x, chip_y, processor_id):
                vertex = placements.get_vertex_on_processor(
                    chip_x, chip_y, processor_id)

                if isinstance(
                        vertex, AbstractSupportsBitFieldRoutingCompression):
                    most_costly_cores[processor_id] = len(
                        machine_graph.get_edges_ending_at_vertex(vertex))

        # get cores that are the most likely to have the worst time and order
        #  bitfields accordingly
        cores = list(most_costly_cores.keys())
        cores = sorted(cores, key=lambda k: most_costly_cores[k], reverse=True)

        # only add bit fields from the worst affected cores, which will
        # build as more and more are taken to make the worst a collection
        # instead of a individual
        cores_to_add_for = list()
        for worst_core_id in range(0, len(cores) - 1):

            # determine how many of the worst to add before it balances with
            # next one
            cores_to_add_for.append(cores[worst_core_id])
            diff = (
                most_costly_cores[cores[worst_core_id]] -
                most_costly_cores[cores[worst_core_id + 1]])

            # order over most effective bitfields
            coverage = processor_coverage_by_bitfield[cores[worst_core_id]]
            coverage.sort(reverse=True)

            # cycle till at least the diff is covered
            covered = 0
            for redundant_packet_count in coverage:
                to_delete = list()
                for bit_field_data in bit_fields_by_coverage[
                        redundant_packet_count]:
                    if bit_field_data.processor_id in cores_to_add_for:
                        if covered < diff:
                            bit_field_data.sort_index = sort_index
                            sort_index += 1
                            to_delete.append(bit_field_data)
                            covered += 1
                for bit_field_data in to_delete:
                    bit_fields_by_coverage[redundant_packet_count].remove(
                        bit_field_data)

        # take left overs
        coverage_levels = list(bit_fields_by_coverage.keys())
        coverage_levels.sort(reverse=True)
        for coverage_level in coverage_levels:
            for bit_field_data in bit_fields_by_coverage[coverage_level]:
                bit_field_data.sort_index = sort_index
                sort_index += 1

        self._n_bitfields = sort_index

    def _start_binary_search(
            self, router_table, target_length, key_atom_map):
        """ start binary search of the merging of bitfield to router table

        :param ~.UnCompressedMulticastRoutingTable router_table:
            uncompressed router table
        :param int target_length: length to compress to
        :param dict(int,int) key_atom_map: map from key to atoms
        """
        # try first just uncompressed. so see if its possible
        try:
            self._best_routing_entries = self._run_algorithm(
                router_table, target_length)
            self._best_midpoint = 0
            self._compression_attempts[0] = "succcess"
        except MinimisationFailedError as e:
            raise PacmanAlgorithmFailedToGenerateOutputsException(
                "host bitfield router compressor can't compress the "
                "uncompressed routing tables, regardless of bitfield merging. "
                "System is fundamentally flawed here") from e

        find_max_success(self._n_bitfields, functools.partial(
            self._binary_search_check, routing_table=router_table,
            target_length=target_length,
            key_to_n_atoms_map=key_atom_map))

    def _binary_search_check(
            self, mid_point, routing_table, target_length, key_to_n_atoms_map):
        """ check function for fix max success

        :param int mid_point: the point if the list to stop at
        :param ~.UnCompressedMulticastRoutingTable routing_table:
            the basic routing table
        :param int target_length: the target length to reach
        :param dict(int,int) key_to_n_atoms_map:
        :return: true if it compresses
        :rtype: bool
        """

        # convert bitfields into router tables
        bit_field_router_table = self._convert_bitfields_into_router_table(
            routing_table, mid_point, key_to_n_atoms_map)

        # try to compress
        try:
            self._best_routing_entries = self._run_algorithm(
                bit_field_router_table, target_length)
            self._best_midpoint = mid_point
            self._compression_attempts[mid_point] = "succcess"
            return True
        except MinimisationFailedError:
            self._compression_attempts[mid_point] = "fail"
            return False
        except PacmanElementAllocationException:
            self._compression_attempts[mid_point] = "Exception"
            return False

    def _run_algorithm(self, router_table, target_length):
        """ Attempts to covert the mega router tables into 1 router table.

        :param list(~.AbsractMulticastRoutingTable) router_table:
            the set of router tables that together need to
            be merged into 1 router table
        :param int target_length: the number
        :return: compressor router table
        :rtype: list(RoutingTableEntry)
        :throws MinimisationFailedError: if it fails to
            compress to the correct length.

        """
        compressor = PairCompressor(ordered=True)
        compressed_entries = compressor.compress_table(router_table)
        if len(compressed_entries) > target_length:
            raise MinimisationFailedError("{} > {}".format(
                len(compressed_entries), target_length))
        return compressed_entries

    def _run_mundy_algorithm(
            self, router_table, target_length):
        """ Attempts to covert the mega router tables into 1 router table.\
            Will raise a MinimisationFailedError exception if it fails to\
            compress to the correct length.

        Note: This method is uncurrently unused

        :param list(~.AbsractMulticastRoutingTable) router_table:
            the set of router tables that together need to
            be merged into 1 router table
        :param int target_length: the number
        :return: compressor router table
        :rtype: list(RoutingTableEntry)
        :throws MinimisationFailedError: If compression fails
        """
        # convert to rig format
        entries = list()
        for router_entry in router_table.multicast_routing_entries:
            # Add the new entry
            entries.append(Entry.from_MulticastRoutingEntry(router_entry))

        # compress the router entries using rigs compressor
        return minimise(entries, target_length)

    def _remove_merged_bitfields_from_cores(self, chip_x, chip_y, transceiver):
        """ Goes to SDRAM and removes said merged entries from the cores' \
            bitfield region

        :param int chip_x: the chip x coord from which this happened
        :param int chip_y: the chip y coord from which this happened
        :param ~.Transceiver transceiver: spinnman instance
        """
        for entries in self._bit_fields_by_key.values():
            for entry in entries:
                if entry.sort_index < self._best_midpoint:
                    # set merged
                    n_atoms_word = entry.n_atoms_word | self.MERGED_SETTER
                    transceiver.write_memory(
                        chip_x, chip_y, entry.n_atoms_address, n_atoms_word)

    def _create_table_report(self, router_table, report_out):
        """ creates the report entry

        :param ~.AbsractMulticastRoutingTable router_table:
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

        percentage_done = 100
        if n_possible_bit_fields != 0:
            percentage_done = (
                (100.0 / float(n_possible_bit_fields)) *
                float(n_bit_fields_merged))

        report_out.write(
            "\nTable {}:{} has integrated {} out of {} available chip level "
            "bitfields into the routing table. There by producing a "
            "compression of {}%.\n\n".format(
                router_table.x, router_table.y, n_bit_fields_merged,
                n_possible_bit_fields, percentage_done))

        report_out.write(
            "The uncompressed routing table had {} entries, the compressed "
            "one with {} integrated bitfields has {} entries. \n\n".format(
                router_table.number_of_entries,
                n_bit_fields_merged,
                # Note: _best_routing_table is a list(), router_table is not
                len(self._best_routing_entries)))

        report_out.write(
            "The integration of {} bitfields removes up to {} MC packets "
            "that otherwise would be being processed by the cores on the "
            "chip, just to be dropped as they do not target anything.\n\n"
            "".format(n_bit_fields_merged, n_packets_filtered))

        report_out.write("The compression attempts are as follows:\n\n")
        for mid_point, result in self._compression_attempts.items():
            report_out.write("Midpoint {}: {}\n".format(mid_point, result))

        report_out.write("\nThe bit_fields merged are as follows:\n\n")

        for core in merged_by_core:
            for bf_data in merged_by_core[core]:
                report_out.write("bitfield on core {} for key {} \n".format(
                    core, bf_data.master_pop_key))

        report_out.write("\n\n\n")
        report_out.write("The final routing table entries are as follows:\n\n")

        report_out.write(
            "{: <5s} {: <10s} {: <10s} {: <10s} {: <7s} {}\n".format(
                "Index", "Key", "Mask", "Route", "Default", "[Cores][Links]"))
        report_out.write(
            "{:-<5s} {:-<10s} {:-<10s} {:-<10s} {:-<7s} {:-<14s}\n".format(
                "", "", "", "", "", ""))
        line_format = "{: >5d} {}\n"

        entry_count = 0
        n_defaultable = 0
        # Note: _best_routing_table is a list(), router_table is not
        for entry in self._best_routing_entries:
            index = entry_count & self._LOWER_16_BITS
            entry_str = line_format.format(index, format_route(
                entry.to_MulticastRoutingEntry()))
            entry_count += 1
            if entry.defaultable:
                n_defaultable += 1
            report_out.write(entry_str)
        report_out.write("{} Defaultable entries\n".format(n_defaultable))
