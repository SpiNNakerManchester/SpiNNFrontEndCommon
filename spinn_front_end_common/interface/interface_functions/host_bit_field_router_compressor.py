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

from __future__ import division

import functools
import math
import os
import struct
from collections import defaultdict

from pacman.exceptions import \
    PacmanAlgorithmFailedToGenerateOutputsException, \
    PacmanElementAllocationException
from pacman.model.routing_tables import MulticastRoutingTables, \
    UnCompressedMulticastRoutingTable
from pacman.operations.router_compressors.mundys_router_compressor.exceptions\
    import MinimisationFailedError
from pacman.operations.algorithm_reports.reports import format_route
from pacman.operations.router_compressors.mundys_router_compressor. \
    routing_table_condenser import MundyRouterCompressor
from pacman.operations.router_compressors.mundys_router_compressor \
    import ordered_covering as rigs_compressor
from spinn_front_end_common.abstract_models import \
    AbstractProvidesNKeysForPartition
from spinn_front_end_common.abstract_models.\
    abstract_supports_bit_field_routing_compression import \
    AbstractSupportsBitFieldRoutingCompression
from spinn_machine import MulticastRoutingEntry
from spinn_utilities.default_ordered_dict import DefaultOrderedDict
from spinn_utilities.find_max_success import find_max_success
from spinn_utilities.progress_bar import ProgressBar


class _BitFieldData(object):

    def __init__(self, processor_id, bit_field, master_pop_key):
        self._processor_id = processor_id
        self._bit_field = bit_field
        self._master_pop_key = master_pop_key

    @property
    def processor_id(self):
        return self._processor_id

    @property
    def bit_field(self):
        return self._bit_field

    @property
    def master_pop_key(self):
        return self._master_pop_key


class HostBasedBitFieldRouterCompressor(object):
    """ host based fancy router compressor using the bitfield filters of the \
    cores.
    """

    __slots__ = [
        "_best_routing_table",
        "_best_bit_fields_by_processor",
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

    # bytes per word
    _BYTES_PER_WORD = 4

    # key id for the initial entry
    _ORIGINAL_ENTRY = 0

    # key id for the bitfield entries
    _ENTRIES = 1

    # bits in a word
    _BITS_IN_A_WORD = 32

    # size of a filter info in bytes (key, n words, pointer)
    _SIZE_OF_FILTER_INFO_IN_BYTES = 12

    # bit to mask a bit
    _BIT_MASK = 1

    # mask for neuron level
    _NEURON_LEVEL_MASK = 0xFFFFFFFF

    # structs for performance requirements.
    _ONE_WORDS = struct.Struct("<I")
    _THREE_WORDS = struct.Struct("<III")

    # for router report
    _LOWER_16_BITS = 0xFFFF

    # rob paul to pay sam threshold starting point at 1ms time step
    _N_PACKETS_PER_SECOND = 100000

    # convert between milliseconds and second
    _MS_TO_SEC = 1000

    # fraction effect for threshold
    _THRESHOLD_FRACTION_EFFECT = 2

    def __init__(self):
        self._best_routing_table = None
        self._best_bit_fields_by_processor = None

    def __call__(
            self, router_tables, machine, placements, transceiver,
            default_report_folder, produce_report,
            use_timer_cut_off, machine_graph, routing_infos,
            machine_time_step, time_scale_factor, target_length=None,
            time_to_try_for_each_iteration=None, graph_mapper=None):
        """ compresses bitfields and router table entries together as /
        feasible as possible

        :param router_tables: routing tables (uncompressed)
        :param machine: SpiNNMachine instance
        :param placements: placements
        :param transceiver: SpiNNMan instance
        :param graph_mapper: mapping between graphs
        :param produce_report: boolean flag for producing report
        :param default_report_folder: report folder
        :param machine_time_step: time step
        :type machine_time_step: int
        :param time_scale_factor: time scale factor
        :type time_scale_factor: int
        :param machine_graph: the machine graph level
        :param target_length: length of table entries to get to.
        :param use_timer_cut_off: bool flag for using timer or not for \
            compressor
        :return: compressed routing table entries
        """

        if target_length is None:
            target_length = self._MAX_SUPPORTED_LENGTH

        if time_to_try_for_each_iteration is None:
            time_to_try_for_each_iteration = self._DEFAULT_TIME_PER_ITERATION

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
            machine_graph, routing_infos, graph_mapper)

        # holder for the bitfields in
        bit_field_sdram_base_addresses = defaultdict(dict)
        for router_table in progress.over(router_tables.routing_tables, False):
            self.collect_bit_field_sdram_base_addresses(
                router_table.x, router_table.y, machine, placements,
                transceiver, graph_mapper, bit_field_sdram_base_addresses)

        # start the routing table choice conversion
        for router_table in progress.over(router_tables.routing_tables):
            self.start_compression_selection_process(
                router_table, produce_report, report_folder_path,
                bit_field_sdram_base_addresses, transceiver, machine_graph,
                placements, machine, graph_mapper, target_length,
                time_to_try_for_each_iteration, use_timer_cut_off,
                compressed_pacman_router_tables, key_atom_map)
        # return compressed tables
        return compressed_pacman_router_tables

    def collect_bit_field_sdram_base_addresses(
            self, chip_x, chip_y, machine, placements, transceiver,
            graph_mapper, bit_field_sdram_base_addresses):

        # locate the bitfields in a chip level scope
        n_processors_on_chip = machine.get_chip_at(chip_x, chip_y).n_processors
        for processor_id in range(0, n_processors_on_chip):
            if placements.is_processor_occupied(chip_x, chip_y, processor_id):
                machine_vertex = placements.get_vertex_on_processor(
                    chip_x, chip_y, processor_id)

                # locate api vertex
                api_vertex = self.locate_vertex_with_the_api(
                    machine_vertex, graph_mapper)

                # get data
                if api_vertex is not None:
                    bit_field_sdram_base_addresses[
                        (chip_x, chip_y)][processor_id] = \
                        api_vertex.bit_field_base_address(
                            transceiver, placements.get_placement_of_vertex(
                                machine_vertex))

    def calculate_threshold(self, machine_time_step, time_scale_factor):
        return(
            ((int(math.floor(machine_time_step / self._MS_TO_SEC))) *
             time_scale_factor * self._N_PACKETS_PER_SECOND) /
            self._THRESHOLD_FRACTION_EFFECT)

    @staticmethod
    def generate_key_to_atom_map(machine_graph, routing_infos, graph_mapper):
        """ THIS IS NEEDED due to the link from key to edge being lost.

        :param machine_graph: machine graph
        :param routing_infos: routing infos
        :param graph_mapper: graph mapper
        :return: key to atom map based of key to n atoms
        """
        # build key to n atoms map
        key_to_n_atoms_map = dict()
        for vertex in machine_graph.vertices:
            for outgoing_partition in \
                    machine_graph.\
                    get_outgoing_edge_partitions_starting_at_vertex(vertex):
                key = routing_infos.get_first_key_from_pre_vertex(
                    vertex, outgoing_partition.identifier)

                if graph_mapper is not None:
                    app_vertex = graph_mapper.get_application_vertex(vertex)
                    if isinstance(
                            app_vertex, AbstractProvidesNKeysForPartition):
                        key_to_n_atoms_map[key] = \
                            app_vertex.get_n_keys_for_partition(
                                outgoing_partition, graph_mapper)
                    else:
                        key_to_n_atoms_map[key] = \
                            graph_mapper.get_slice(vertex).n_atoms
                else:
                    if isinstance(vertex, AbstractProvidesNKeysForPartition):
                        key_to_n_atoms_map[key] = \
                            vertex.get_n_keys_for_partition(
                                outgoing_partition, None)
                    else:
                        key_to_n_atoms_map[
                            routing_infos.get_first_key_from_pre_vertex(
                                vertex, outgoing_partition.identifier)] = 1
        return key_to_n_atoms_map

    def generate_report_path(self, default_report_folder):
        report_folder_path = \
            os.path.join(default_report_folder, self._REPORT_FOLDER_NAME)
        if not os.path.exists(report_folder_path):
            os.mkdir(report_folder_path)
        return report_folder_path

    def start_compression_selection_process(
            self, router_table, produce_report, report_folder_path,
            bit_field_sdram_base_addresses, transceiver, machine_graph,
            placements, machine, graph_mapper, target_length,
            time_to_try_for_each_iteration, use_timer_cut_off,
            compressed_pacman_router_tables, key_atom_map):
        """ entrance method for doing on host compression. Utilisable as a \
        public method for other compressors.

        :param router_table: the routing table in question to compress
        :param produce_report: bool flag if the report should be generated
        :param report_folder_path: the report folder base address
        :param bit_field_sdram_base_addresses: the sdram addresses for \
            bitfields used in the chip.
        :param transceiver: spinnMan instance
        :param machine_graph: machine graph
        :param placements: placements
        :param machine: SpiNNMan instance
        :param graph_mapper: mapping between 2 graphs
        :param target_length: length of router compressor to get to
        :param time_to_try_for_each_iteration: time in seconds to run each \
        compression attempt for
        :param use_timer_cut_off: bool flag that indicates if the timer cut \
        off is to be used
        :param key_atom_map: key to atoms map
        should be allowed to handle per time step
        :param compressed_pacman_router_tables: a data holder for compressed \
        tables
        :return: None
        """

        # create report file
        report_out = None
        if produce_report:
            report_file_path = os.path.join(
                report_folder_path,
                self._REPORT_NAME.format(router_table.x, router_table.y))
            report_out = open(report_file_path, "w")

        # iterate through bitfields on this chip and convert to router
        # table
        bit_field_chip_base_addresses = bit_field_sdram_base_addresses[
            (router_table.x, router_table.y)]

        # read in bitfields.
        bit_fields_by_processor, sorted_bit_fields = \
            self._read_in_bit_fields(
                transceiver, router_table.x, router_table.y,
                bit_field_chip_base_addresses, machine_graph,
                placements, machine.get_chip_at(
                    router_table.x, router_table.y).n_processors,
                graph_mapper)

        # execute binary search
        self._start_binary_search(
            router_table, sorted_bit_fields, target_length,
            time_to_try_for_each_iteration, use_timer_cut_off, key_atom_map)

        # add final to compressed tables
        compressed_pacman_router_tables.add_routing_table(
            self._best_routing_table)

        # remove bitfields from cores that have been merged into the
        # router table
        self._remove_merged_bitfields_from_cores(
            self._best_bit_fields_by_processor, router_table.x,
            router_table.y, transceiver,
            bit_field_chip_base_addresses, bit_fields_by_processor)

        # report
        if produce_report:
            self._create_table_report(
                router_table, sorted_bit_fields, report_out)
            report_out.flush()
            report_out.close()

    def _convert_bitfields_into_router_tables(
            self, router_table, bitfields_by_key, key_to_n_atoms_map):
        """ converts the bitfield into router table entries for compression. \
        based off the entry located in the original router table

        :param router_table: the original routing table
        :param bitfields_by_key: the bitfields of the chip.
        :return: routing tables.
        """
        bit_field_router_tables = list()

        # clone the original entries
        original_route_entries = list()
        original_route_entries.extend(router_table.multicast_routing_entries)

        # go through the bitfields and get the routing table for it
        for master_pop_key in bitfields_by_key.keys():

            bit_field_original_entry = \
                router_table.get_entry_by_routing_entry_key(master_pop_key)
            bit_field_entries = \
                UnCompressedMulticastRoutingTable(
                    router_table.x, router_table.y,
                    multicast_routing_entries=(
                        self._generate_entries_from_bitfield(
                            bitfields_by_key[master_pop_key],
                            bit_field_original_entry, key_to_n_atoms_map)))

            # add to the list
            bit_field_router_tables.append(bit_field_entries)

            # remove entry
            original_route_entries.remove(bit_field_original_entry)

        # create reduced
        reduced_original_table = UnCompressedMulticastRoutingTable(
            router_table.x, router_table.y, original_route_entries)

        # add reduced to front of the tables
        bit_field_router_tables.insert(0, reduced_original_table)

        # return the bitfield tables and the reduced original table
        return bit_field_router_tables

    def _generate_entries_from_bitfield(
            self, bit_fields, routing_table_entry, key_to_n_atoms_map):
        """ generate neuron level entries

        :param bit_fields: the bitfields for a given key
        :param routing_table_entry: the original entry from it
        :return: the set of bitfield entries
        """

        entries = list()

        processors_filtered = list()

        for bit_field_by_processor in bit_fields:
            processors_filtered.append(bit_field_by_processor.processor_id)

        # get some basic values
        entry_links = routing_table_entry.link_ids
        base_key = routing_table_entry.routing_entry_key
        n_neurons = key_to_n_atoms_map[base_key]

        # check each neuron to see if any bitfields care, and if so,
        # add processor
        for neuron in range(0, n_neurons):
            processors = list()

            # add processors that are not going to be filtered
            for processor_id in routing_table_entry.processor_ids:
                if processor_id not in processors_filtered:
                    processors.append(processor_id)

            # process bitfields
            for bit_field_by_processor in bit_fields:
                if self._bit_for_neuron_id(
                        bit_field_by_processor.bit_field, neuron):
                    processors.append(bit_field_by_processor.processor_id)

            # build new entry for this neuron
            entries.append(MulticastRoutingEntry(
                routing_entry_key=base_key + neuron,
                mask=self._NEURON_LEVEL_MASK, link_ids=entry_links,
                defaultable=False, processor_ids=processors))

        # return the entries
        return entries

    def _bit_for_neuron_id(self, bit_field, neuron_id):
        """ locate the bit for the neuron in the bitfield

        :param bit_field: the block of words which represent the bitfield
        :param neuron_id: the neuron id to find the bit in the bitfield
        :return: the bit
        """
        word_id = int(neuron_id // self._BITS_IN_A_WORD)
        bit_in_word = neuron_id % self._BITS_IN_A_WORD
        try:
            flag = (bit_field[word_id] >> bit_in_word) & self._BIT_MASK
            return flag
        except Exception:
            print(
                "failed to read word {} and shifting {} bits as words "
                "length is {} neuron id {} for n neurons of {}".format(
                    word_id, bit_in_word, len(bit_field), neuron_id,
                    len(bit_field) * self._BITS_IN_A_WORD))
            import sys
            sys.exit()

    def _read_in_bit_fields(
            self, transceiver, chip_x, chip_y, bit_field_chip_base_addresses,
            machine_graph, placements, n_processors_on_chip, graph_mapper):
        """ reads in the bitfields from the cores

        :param transceiver: SpiNNMan instance
        :param chip_x: chip x coord
        :param chip_y: chip y coord
        :param machine_graph: machine graph
        :param placements: the placements
        :param graph_mapper: the mapping between graphs
        :param n_processors_on_chip: the number of processors on this chip
        :param bit_field_chip_base_addresses: dict of core id to base address
        :return: dict of lists of processor id to bitfields.
        """

        # data holder
        bit_fields_by_processor = defaultdict(list)
        bit_fields_by_coverage = defaultdict(list)
        processor_coverage_by_bitfield = defaultdict(list)

        # read in for each app vertex that would have a bitfield
        for processor_id in bit_field_chip_base_addresses.keys():
            bit_field_base_address = \
                bit_field_chip_base_addresses[processor_id]

            # read how many bitfields there are
            n_bit_field_entries = struct.unpack("<I", transceiver.read_memory(
                chip_x, chip_y, bit_field_base_address,
                self._BYTES_PER_WORD))[0]
            reading_address = bit_field_base_address + self._BYTES_PER_WORD

            # read in each bitfield
            for bit_field_index in range(0, n_bit_field_entries):
                # master pop key, n words and read pointer
                (master_pop_key, n_words_to_read, read_pointer) = \
                    struct.unpack(
                        "<III", transceiver.read_memory(
                            chip_x, chip_y, reading_address,
                            self._BYTES_PER_WORD * 3))
                reading_address += self._BYTES_PER_WORD * 3

                # get bitfield words
                bit_field = struct.unpack(
                    "<{}I".format(n_words_to_read),
                    transceiver.read_memory(
                        chip_x, chip_y, read_pointer,
                        n_words_to_read * self._BYTES_PER_WORD))

                n_redundant_packets = self._detect_redundant_packet_count(
                    bit_field)

                # sorted by best coverage of redundant packets
                data = _BitFieldData(processor_id, bit_field, master_pop_key)
                bit_fields_by_coverage[n_redundant_packets].append(data)
                processor_coverage_by_bitfield[processor_id].append(
                    n_redundant_packets)

                # add to the bitfields tracker
                bit_fields_by_processor[processor_id].append(data)

        # use the ordered process to find the best ones to do first
        list_of_bitfields_in_impact_order = self._order_bit_fields(
            bit_fields_by_coverage, machine_graph, chip_x, chip_y, placements,
            n_processors_on_chip, graph_mapper, processor_coverage_by_bitfield)

        return bit_fields_by_processor, list_of_bitfields_in_impact_order

    @staticmethod
    def locate_vertex_with_the_api(machine_vertex, graph_mapper):
        if isinstance(
                machine_vertex, AbstractSupportsBitFieldRoutingCompression):
            return machine_vertex
        elif graph_mapper is not None:
            app_vertex = graph_mapper.get_application_vertex(machine_vertex)
            if isinstance(
                    app_vertex, AbstractSupportsBitFieldRoutingCompression):
                return app_vertex
        else:
            return None

    def _order_bit_fields(
            self, bit_fields_by_coverage, machine_graph, chip_x, chip_y,
            placements, n_processors_on_chip, graph_mapper,
            processor_coverage_by_bitfield):

        sorted_bit_fields = list()

        # get incoming bandwidth for the cores
        most_costly_cores = dict()
        for processor_id in range(0, n_processors_on_chip):
            if placements.is_processor_occupied(chip_x, chip_y, processor_id):
                vertex = placements.get_vertex_on_processor(
                    chip_x, chip_y, processor_id)

                valid = self.locate_vertex_with_the_api(
                    vertex, graph_mapper)
                if valid is not None:
                    most_costly_cores[processor_id] = \
                        len(machine_graph.get_edges_ending_at_vertex(vertex))

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
                            to_delete.append(bit_field_data)
                            sorted_bit_fields.append(bit_field_data)
                            covered += 1
                for bit_field_data in to_delete:
                    bit_fields_by_coverage[redundant_packet_count].remove(
                        bit_field_data)

        # take left overs
        coverage_levels = list(bit_fields_by_coverage.keys())
        coverage_levels.sort(reverse=True)
        for coverage_level in coverage_levels:
            for bit_field_data in bit_fields_by_coverage[coverage_level]:
                sorted_bit_fields.append(bit_field_data)

        return sorted_bit_fields

    def _detect_redundant_packet_count(self, bitfield):
        """ locate in the bitfield how many possible packets it can filter /
        away when integrated into the router table.

        :param bitfield: the memory blocks that represent the bitfield
        :return: the number of redundant packets being captured.
        """
        n_packets_filtered = 0
        n_neurons = len(bitfield) * self._BITS_IN_A_WORD

        for neuron_id in range(0, n_neurons):
            if self._bit_for_neuron_id(bitfield, neuron_id) == 0:
                n_packets_filtered += 1
        return n_packets_filtered

    def _start_binary_search(
            self, router_table, sorted_bit_fields, target_length,
            time_to_try_for_each_iteration, use_timer_cut_off, key_atom_map):
        """ start binary search of the merging of bitfield to router table

        :param router_table: uncompressed router table
        :param sorted_bit_fields: the sorted bitfields
        :param target_length: length to compress to
        :param time_to_try_for_each_iteration: the time to allow compressor \
            to run for.
        :param use_timer_cut_off: bool flag for if we should use the timer \
            cutoff for compression
        :param key_atom_map: map from key to atoms
        :return: final_routing_table, bit_fields_merged
        """

        # try first just uncompressed. so see if its possible
        try:
            self._best_routing_table = self._run_algorithm(
                [router_table], target_length, router_table.x, router_table.y,
                time_to_try_for_each_iteration, use_timer_cut_off)
            self._best_bit_fields_by_processor = []
        except MinimisationFailedError:
            raise PacmanAlgorithmFailedToGenerateOutputsException(
                "host bitfield router compressor cant compress the "
                "uncompressed routing tables, regardless of bitfield merging. "
                "System is fundamentally flawed here")

        find_max_success(len(sorted_bit_fields), functools.partial(
            self._binary_search_check, sorted_bit_fields=sorted_bit_fields,
            routing_table=router_table, target_length=target_length,
            time_to_try_for_each_iteration=time_to_try_for_each_iteration,
            use_timer_cut_off=use_timer_cut_off,
            key_to_n_atoms_map=key_atom_map))

    def _binary_search_check(
            self, mid_point, sorted_bit_fields, routing_table, target_length,
            time_to_try_for_each_iteration, use_timer_cut_off,
            key_to_n_atoms_map):
        """ check function for fix max success

        :param mid_point: the point if the list to stop at
        :param sorted_bit_fields: lists of bitfields
        :param routing_table: the basic routing table
        :param target_length: the target length to reach
        :param time_to_try_for_each_iteration: the time in seconds to run for
        :param use_timer_cut_off: bool for if the timer cutoff should be \
            used by the compressor.
        :return: bool that is true if it compresses
        """

        # find new set of bitfields to try from midpoint
        new_bit_field_by_processor = DefaultOrderedDict(list)

        for element in range(0, mid_point):
            bf_data = sorted_bit_fields[element]
            new_bit_field_by_processor[bf_data.master_pop_key].append(bf_data)

        # convert bitfields into router tables
        bit_field_router_tables = self._convert_bitfields_into_router_tables(
            routing_table, new_bit_field_by_processor, key_to_n_atoms_map)

        # try to compress
        try:
            self._best_routing_table = \
                self._run_algorithm(
                    bit_field_router_tables, target_length, routing_table.x,
                    routing_table.y, time_to_try_for_each_iteration,
                    use_timer_cut_off)
            self._best_bit_fields_by_processor = \
                new_bit_field_by_processor
            return True
        except MinimisationFailedError:
            return False
        except PacmanElementAllocationException:
            return False

    def _run_algorithm(
            self, router_tables, target_length, chip_x, chip_y,
            time_to_try_for_each_iteration, use_timer_cut_off):
        """ attempts to covert the mega router tables into 1 router table. will\
        raise a MinimisationFailedError exception if it fails to compress to \
        the correct length

        :param router_tables: the set of router tables that together need to \
        be merged into 1 router table
        :param target_length: the number
        :param chip_x:  chip x
        :param chip_y: chip y
        :param time_to_try_for_each_iteration: time for compressor to run for
        :param use_timer_cut_off: bool flag for using timer cutoff
        :return: compressor router table
        :throws: MinimisationFailedError
        """

        # convert to rig format
        entries = list()
        for router_table in router_tables:
            entries.extend(MundyRouterCompressor.convert_to_mundy_format(
                router_table))

        # compress the router entries using rigs compressor
        compressed_router_table_entries = rigs_compressor.minimise(
            entries, target_length, time_to_try_for_each_iteration,
            use_timer_cut_off)

        # convert back to pacman model
        compressed_pacman_table = \
            MundyRouterCompressor.convert_to_pacman_router_table(
                compressed_router_table_entries, chip_x, chip_y,
                self._MAX_SUPPORTED_LENGTH)

        return compressed_pacman_table

    def _remove_merged_bitfields_from_cores(
            self, bit_fields_merged, chip_x, chip_y, transceiver,
            bit_field_base_addresses, bit_fields_by_processor):
        """ goes to sdram and removes said merged entries from the cores \
        bitfield region

        :param bit_fields_merged: the bitfields that were merged into router \
        table
        :param chip_x: the chip x coord from which this happened
        :param chip_y: the chip y coord from which this happened
        :param transceiver: spinnman instance
        :param bit_field_base_addresses: base addresses of chip bit fields
        :param bit_fields_by_processor: map of processor to bitfields
        :rtype: None
        """

        # get data back ina  form useful for write back
        new_bit_field_by_processor = defaultdict(list)
        for master_pop_key in bit_fields_merged:
            for bit_field_by_processor in bit_fields_merged[master_pop_key]:
                new_bit_field_by_processor[
                    bit_field_by_processor.processor_id].append(master_pop_key)

        # process the separate cores
        for processor_id in bit_fields_by_processor.keys():

            # amount of entries to remove
            new_total = (
                len(bit_fields_by_processor[processor_id]) -
                len(new_bit_field_by_processor[processor_id]))

            # base address for the region
            bit_field_base_address = bit_field_base_addresses[processor_id]
            writing_address = bit_field_base_address
            words_writing_address = (
                writing_address + (
                    new_total * self._SIZE_OF_FILTER_INFO_IN_BYTES))

            # write correct number of elements.
            transceiver.write_memory(
                chip_x, chip_y, writing_address, self._ONE_WORDS.pack(
                    new_total), self._BYTES_PER_WORD)
            writing_address += self._BYTES_PER_WORD

            # iterate through the original bitfields and omit the ones deleted
            for bf_by_key in bit_fields_by_processor[processor_id]:
                if bf_by_key.master_pop_key not in \
                        new_bit_field_by_processor[bf_by_key.processor_id]:

                    # write key and n words
                    transceiver.write_memory(
                        chip_x, chip_y, writing_address,
                        self._THREE_WORDS.pack(
                            bf_by_key.master_pop_key,
                            len(bf_by_key.bit_field), words_writing_address),
                        self._SIZE_OF_FILTER_INFO_IN_BYTES)
                    writing_address += self._SIZE_OF_FILTER_INFO_IN_BYTES

                    # write bitfield words
                    data = struct.pack(
                        "<{}I".format(len(bf_by_key.bit_field)),
                        *bf_by_key.bit_field)
                    transceiver.write_memory(
                        chip_x, chip_y, words_writing_address, data,
                        len(bf_by_key.bit_field) * self._BYTES_PER_WORD)
                    words_writing_address += len(
                        bf_by_key.bit_field) * self._BYTES_PER_WORD

    def _create_table_report(
            self, router_table, sorted_bit_fields, report_out):
        """ creates the report entry

        :param router_table: the uncompressed router table to process
        :param sorted_bit_fields: the bitfields overall
        :param report_out: the report writer
        :rtype: None
        """

        n_bit_fields_merged = 0
        for key in self._best_bit_fields_by_processor.keys():
            n_bit_fields_merged += len(self._best_bit_fields_by_processor[key])

        n_packets_filtered = 0
        for key in self._best_bit_fields_by_processor.keys():
            for element in self._best_bit_fields_by_processor[key]:
                n_neurons = len(element.bit_field) * self._BITS_IN_A_WORD
                for neuron_id in range(0, n_neurons):
                    is_set = self._bit_for_neuron_id(
                        element.bit_field, neuron_id)
                    if is_set == 0:
                        n_packets_filtered += 1

        n_possible_bit_fields = len(sorted_bit_fields)

        percentage_done = 100
        if n_possible_bit_fields != 0:
            percentage_done = (
                (100.0 / float(n_possible_bit_fields)) *
                float(n_bit_fields_merged))

        report_out.write(
            "Table{}:{} has integrated {} out of {} available chip level "
            "bitfields into the routing table. There by producing a "
            "compression of {}%.\n\n".format(
                router_table.x, router_table.y, n_bit_fields_merged,
                n_possible_bit_fields, percentage_done))

        report_out.write(
            "The uncompressed routing table had {} entries, the compressed "
            "one with {} integrated bitfields has {} entries. \n\n".format(
                router_table.number_of_entries,
                self._best_routing_table.number_of_entries,
                n_bit_fields_merged))

        report_out.write(
            "The integration of {} bitfields removes up to {} MC packets "
            "that otherwise would be being processed by the cores on the "
            "chip, just to be dropped as they do not target anything.".format(
                n_bit_fields_merged, n_packets_filtered))

        report_out.write("The bit_fields merged are as follows:\n\n")

        for key in self._best_bit_fields_by_processor.keys():
            for bf_by_processor in self._best_bit_fields_by_processor[key]:
                report_out.write("bitfield on core {} for key {} \n".format(
                    bf_by_processor.processor_id, key))

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
        for entry in self._best_routing_table.multicast_routing_entries:
            index = entry_count & self._LOWER_16_BITS
            entry_str = line_format.format(index, format_route(entry))
            entry_count += 1
            if entry.defaultable:
                n_defaultable += 1
            report_out.write(entry_str)
        report_out.write("{} Defaultable entries\n".format(n_defaultable))
