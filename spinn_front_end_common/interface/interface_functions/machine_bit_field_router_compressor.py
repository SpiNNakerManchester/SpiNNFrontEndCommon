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
import logging
import struct
from collections import defaultdict

from pacman.model.routing_tables import MulticastRoutingTables
from pacman.operations.router_compressors.mundys_router_compressor.\
    ordered_covering import get_generality as ordered_covering_generality
from spinn_front_end_common.interface.interface_functions import \
    ChipIOBufExtractor, LoadExecutableImages
from spinn_front_end_common.interface.interface_functions.\
    host_bit_field_router_compressor import \
    HostBasedBitFieldRouterCompressor
from spinn_front_end_common.mapping_algorithms. \
    on_chip_router_table_compression.compression import Compression
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException
from spinn_front_end_common.utilities.utility_objs import ProvenanceDataItem, \
    ExecutableType
from spinn_machine import CoreSubsets, Router
from spinn_utilities.progress_bar import ProgressBar
from spinnman.exceptions import SpinnmanInvalidParameterException, \
    SpinnmanUnexpectedResponseCodeException, SpinnmanException
from spinnman.model import ExecutableTargets
from spinnman.model.enums import CPUState


from spinn_front_end_common.utilities.exceptions import \
    CantFindSDRAMToUseException
from spinn_front_end_common.utilities import system_control_logic

logger = logging.getLogger(__name__)

# sdram allocation for addresses
SIZE_OF_SDRAM_ADDRESS_IN_BYTES = (17 * 2 * 4) + (3 * 4)

SECOND_TO_MICRO_SECOND = 1000000

# provenance data item names
PROV_TOP_NAME = "bit_field_router_provenance"
PROV_CHIP_NAME = "router_at_chip_{}_{}"
MERGED_NAME = "bit_fields_merged"


class MachineBitFieldRouterCompressor(object):

    __slots__ = []

    # sdram tag the router compressor expects to find there routing tables in
    ROUTING_TABLE_SDRAM_TAG = 1

    # sdram tag for the addresses the router compressor expects to find the /
    # bitfield addresses for the chip.
    BIT_FIELD_ADDRESSES_SDRAM_TAG = 2

    #
    TIMES_CYCLED_ROUTING_TABLES = 3

    # the successful identifier
    SUCCESS = 0

    # how many header elements are in the region addresses (1, n addresses)
    N_REGIONS_ELEMENT = 1

    # the number of bytes needed to read the user 2 register
    _USER_BYTES = 4

    # min size a heap object needs in sdram. (limit on the size of useful
    # sdram regions to steal
    _MIN_SIZE_FOR_HEAP = 32

    # structs for performance requirements.
    _FOUR_WORDS = struct.Struct("<IIII")

    _THREE_WORDS = struct.Struct("<III")

    _TWO_WORDS = struct.Struct("<II")

    _ONE_WORDS = struct.Struct("<I")

    # binary names
    _BIT_FIELD_SORTER_AND_SEARCH_EXECUTOR_APLX = \
        "bit_field_sorter_and_searcher.aplx"
    _COMPRESSOR_APLX = "bit_field_compressor.aplx"

    _PROGRESS_BAR_TEXT = \
        "on chip compressing routing tables and merging in bitfields as " \
        "appropriate"

    _ON_CHIP_ERROR_MESSAGE = \
        "The router compressor with bit field on {}, {} failed to complete. " \
        "Will execute host based routing compression instead"

    _ON_HOST_WARNING_MESSAGE = \
        "Will be executing compression for {} chips on the host, as they " \
        "failed to complete when running on chip"

    def __call__(
            self, routing_tables, transceiver, machine, app_id,
            provenance_file_path, machine_graph, placements, executable_finder,
            read_algorithm_iobuf, produce_report, default_report_folder,
            target_length, routing_infos, time_to_try_for_each_iteration,
            use_timer_cut_off, machine_time_step, time_scale_factor,
            no_sync_changes, threshold_percentage,
            executable_targets, graph_mapper=None,
            compress_only_when_needed=True,
            compress_as_much_as_possible=False, provenance_data_objects=None):
        """ entrance for routing table compression with bit field

        :param routing_tables: routing tables
        :param transceiver: spinnman instance
        :param machine: spinnMachine instance
        :param app_id: app id of the application
        :param provenance_file_path: file path for prov data
        :param machine_graph: machine graph
        :param graph_mapper: mapping between graphs (could be none)
        :param placements: placements on machine
        :param threshold_percentage: the percentage of bitfields to do on chip\
         before its considered a success
        :param executable_finder: where are binaries are located
        :param read_algorithm_iobuf: bool flag saying if read iobuf
        :param compress_only_when_needed: bool flag asking if compress only \
        when needed
        :param compress_as_much_as_possible: bool flag asking if should \
        compress as much as possible
        :param executable_targets: the set of targets and executables
        :rtype: executable targets
        """

        # build provenance data objects
        if provenance_data_objects is not None:
            prov_items = provenance_data_objects
        else:
            prov_items = list()

        if len(routing_tables.routing_tables) == 0:
            return ExecutableTargets(), prov_items

        # new app id for this simulation
        routing_table_compressor_app_id = \
            transceiver.app_id_tracker.get_new_id()

        progress_bar = ProgressBar(
            total_number_of_things_to_do=(
                len(machine_graph.vertices) +
                (len(routing_tables.routing_tables) *
                 self.TIMES_CYCLED_ROUTING_TABLES)),
            string_describing_what_being_progressed=self._PROGRESS_BAR_TEXT)

        # locate data and on_chip_cores to load binary on
        (addresses, matrix_addresses_and_size) = self._generate_addresses(
            machine_graph, placements, transceiver, progress_bar, graph_mapper)

        # create executable targets
        (compressor_executable_targets, bit_field_sorter_executable_path,
         bit_field_compressor_executable_path) = self._generate_core_subsets(
            routing_tables, executable_finder, machine, progress_bar,
            executable_targets)

        # load data into sdram
        on_host_chips = self._load_data(
            addresses, transceiver, routing_table_compressor_app_id,
            routing_tables, app_id, compress_only_when_needed, machine,
            compress_as_much_as_possible, progress_bar,
            compressor_executable_targets,
            matrix_addresses_and_size, time_to_try_for_each_iteration,
            bit_field_compressor_executable_path,
            bit_field_sorter_executable_path, threshold_percentage)

        # load and run binaries
        try:
            system_control_logic.run_system_application(
                compressor_executable_targets,
                routing_table_compressor_app_id, transceiver,
                provenance_file_path, executable_finder,
                read_algorithm_iobuf,
                functools.partial(
                    self._check_bit_field_router_compressor_for_success,
                    host_chips=on_host_chips,
                    sorter_binary_path=bit_field_sorter_executable_path,
                    prov_data_items=prov_items),
                functools.partial(
                    self._handle_failure_for_bit_field_router_compressor,
                    host_chips=on_host_chips, txrx=transceiver),
                [CPUState.FINISHED], True, no_sync_changes,
                "bit_field_compressor_on_{}_{}_{}.txt",
                [bit_field_sorter_executable_path])
        except (SpinnmanException, SpinnFrontEndException):
            self._handle_failure_for_bit_field_router_compressor(
                compressor_executable_targets, on_host_chips, transceiver)

        # start the host side compressions if needed
        if len(on_host_chips) != 0:
            logger.warning(
                self._ON_HOST_WARNING_MESSAGE.format(len(on_host_chips)))

            host_compressor = HostBasedBitFieldRouterCompressor()
            compressed_pacman_router_tables = MulticastRoutingTables()

            key_atom_map = host_compressor.generate_key_to_atom_map(
                machine_graph, routing_infos, graph_mapper)

            for (chip_x, chip_y) in progress_bar.over(on_host_chips, False):
                bit_field_sdram_base_addresses = defaultdict(dict)
                host_compressor.collect_bit_field_sdram_base_addresses(
                    chip_x, chip_y, machine, placements, transceiver,
                    graph_mapper, bit_field_sdram_base_addresses)

                host_compressor.start_compression_selection_process(
                    router_table=routing_tables.get_routing_table_for_chip(
                        chip_x, chip_y),
                    produce_report=produce_report,
                    report_folder_path=host_compressor.generate_report_path(
                        default_report_folder),
                    bit_field_sdram_base_addresses=(
                        bit_field_sdram_base_addresses),
                    transceiver=transceiver, machine_graph=machine_graph,
                    placements=placements, machine=machine,
                    graph_mapper=graph_mapper,
                    target_length=target_length,
                    time_to_try_for_each_iteration=(
                        time_to_try_for_each_iteration),
                    use_timer_cut_off=use_timer_cut_off,
                    compressed_pacman_router_tables=(
                        compressed_pacman_router_tables),
                    key_atom_map=key_atom_map)

            # load host compressed routing tables
            for table in compressed_pacman_router_tables.routing_tables:
                if (not machine.get_chip_at(table.x, table.y).virtual
                        and table.multicast_routing_entries):
                    transceiver.load_multicast_routes(
                        table.x, table.y, table.multicast_routing_entries,
                        app_id=app_id)

        # complete progress bar
        progress_bar.end()

        return compressor_executable_targets, prov_items

    def _generate_core_subsets(
            self, routing_tables, executable_finder, machine, progress_bar,
            system_executable_targets):
        """ generates the core subsets for the binaries

        :param routing_tables: the routing tables
        :param executable_finder: the executable path finder
        :param machine: the spinn machine instance
        :param progress_bar: progress bar
        :param system_executable_targets: the executables targets to cores
        :return: tuple of (targets, sorter path and compressor path)
        """
        bit_field_sorter_cores = CoreSubsets()
        bit_field_compressor_cores = CoreSubsets()

        _, cores = LoadExecutableImages.filter_targets(
            system_executable_targets, lambda ty: ty is ExecutableType.SYSTEM)

        for routing_table in progress_bar.over(routing_tables, False):
            # add 1 core to the sorter, and the rest to compressors
            sorter = None
            for processor in machine.get_chip_at(
                    routing_table.x, routing_table.y).processors:
                if (not processor.is_monitor and
                        not cores.all_core_subsets.is_core(
                            routing_table.x, routing_table.y,
                            processor.processor_id)):
                    if sorter is None:
                        sorter = processor
                        bit_field_sorter_cores.add_processor(
                            routing_table.x, routing_table.y,
                            processor.processor_id)
                    else:
                        bit_field_compressor_cores.add_processor(
                            routing_table.x, routing_table.y,
                            processor.processor_id)

        # convert core subsets into executable targets
        executable_targets = ExecutableTargets()

        # bit field executable paths
        bit_field_sorter_executable_path = \
            executable_finder.get_executable_path(
                self._BIT_FIELD_SORTER_AND_SEARCH_EXECUTOR_APLX)

        bit_field_compressor_executable_path = \
            executable_finder.get_executable_path(self._COMPRESSOR_APLX)

        # add the sets
        executable_targets.add_subsets(
            binary=bit_field_sorter_executable_path,
            subsets=bit_field_sorter_cores)
        executable_targets.add_subsets(
            binary=bit_field_compressor_executable_path,
            subsets=bit_field_compressor_cores)

        return (executable_targets, bit_field_sorter_executable_path,
                bit_field_compressor_executable_path)

    def _check_bit_field_router_compressor_for_success(
            self, executable_targets, transceiver, host_chips,
            sorter_binary_path, prov_data_items):
        """ Goes through the cores checking for cores that have failed to\
            generate the compressed routing tables with bitfield

        :param executable_targets: cores to load router compressor with\
         bitfield on
        :param transceiver: SpiNNMan instance
        :param host_chips: the chips which need to be ran on host.
        :param sorter_binary_path: the path to the sorter binary
        :param prov_data_items: the store of data items
        :rtype: None
        """

        sorter_cores = executable_targets.get_cores_for_binary(
            sorter_binary_path)
        for core_subset in sorter_cores:
            x = core_subset.x
            y = core_subset.y

            # prov names
            names = list()
            names.append(PROV_TOP_NAME)
            names.append(PROV_CHIP_NAME.format(x, y))
            names.append(MERGED_NAME)

            for p in core_subset.processor_ids:

                # Read the result from USER1/USER2 registers
                user_1_base_address = \
                    transceiver.get_user_1_register_address_from_core(p)
                user_2_base_address = \
                    transceiver.get_user_2_register_address_from_core(p)
                result = struct.unpack(
                    "<I", transceiver.read_memory(
                        x, y, user_1_base_address, self._USER_BYTES))[0]
                total_bit_fields_merged = struct.unpack(
                    "<I", transceiver.read_memory(
                        x, y, user_2_base_address, self._USER_BYTES))[0]

                if result != self.SUCCESS:
                    if (x, y) not in host_chips:
                        host_chips.append((x, y))
                    return False
                else:
                    prov_data_items.append(ProvenanceDataItem(
                        names, str(total_bit_fields_merged)))
        return True

    @staticmethod
    def _call_iobuf_and_clean_up(
            executable_targets, transceiver, provenance_file_path,
            compressor_app_id, executable_finder):
        """handles the reading of iobuf and cleaning the cores off the machine

        :param executable_targets: cores which are running the router \
        compressor with bitfield.
        :param transceiver: SpiNNMan instance
        :param provenance_file_path: provenance file path
        :param executable_finder: executable finder
        :rtype: None
        """
        iobuf_extractor = ChipIOBufExtractor()
        io_errors, io_warnings = iobuf_extractor(
            transceiver, executable_targets, executable_finder,
            system_provenance_file_path=provenance_file_path,
            app_provenance_file_path=None,
            binary_executable_types=ExecutableType.SYSTEM)
        for warning in io_warnings:
            logger.warning(warning)
        for error in io_errors:
            logger.error(error)
        transceiver.stop_application(compressor_app_id)
        transceiver.app_id_tracker.free_id(compressor_app_id)

    @staticmethod
    def _handle_failure_for_bit_field_router_compressor(
            executable_targets, host_chips, txrx):
        """handles the state where some cores have failed.

        :param executable_targets: cores which are running the router \
        compressor with bitfield.
        :param host_chips: chips which need host based compression
        :param txrx: spinnman instance
        :rtype: None
        """
        logger.info(
            "on chip routing table compressor with bit field has failed")
        for core_subset in executable_targets.all_core_subsets:
            if (core_subset.x, core_subset.y) not in host_chips:
                host_chips.append((core_subset.x, core_subset.y))
        cores = txrx.get_cores_in_state(
            executable_targets.all_core_subsets, [CPUState.RUN_TIME_EXCEPTION])
        logger.info("failed on cores {}".format(cores))

    def _load_data(
            self, addresses, transceiver, routing_table_compressor_app_id,
            routing_tables, app_id, compress_only_when_needed, machine,
            compress_as_much_as_possible, progress_bar, cores,
            matrix_addresses_and_size, time_per_iteration,
            bit_field_compressor_executable_path,
            bit_field_sorter_executable_path, threshold_percentage):
        """ load all data onto the chip

        :param addresses: the addresses for bitfields in sdram
        :param transceiver: the spinnMan instance
        :param routing_table_compressor_app_id: the app id for the system app
        :param routing_tables: the routing tables
        :param app_id: the appid of the application
        :param compress_only_when_needed: bool flag asking if compress only \
        when needed
        :param progress_bar: progress bar
        :param compress_as_much_as_possible: bool flag asking if should \
        compress as much as possible
        :param cores: the cores that compressor will run on
        :param matrix_addresses_and_size: dict of chips to regeneration \
        sdram and size for exploitation
        :param bit_field_compressor_executable_path: the path to the \
        compressor binary path
        :param bit_field_sorter_executable_path: the path to the sorter binary
        :return: the list of tuples saying which chips this will need to use \
        host compression, as the malloc failed.
        :rtype: list of tuples saying which chips this will need to use host \
        compression, as the malloc failed.
        """

        run_by_host = list()
        for table in routing_tables.routing_tables:
            if not machine.get_chip_at(table.x, table.y).virtual:
                try:
                    self._load_routing_table_data(
                        table, app_id, transceiver,
                        routing_table_compressor_app_id, progress_bar, cores,
                        matrix_addresses_and_size[(table.x, table.y)])

                    self._load_address_data(
                        addresses, table.x, table.y, transceiver,
                        routing_table_compressor_app_id,
                        cores, matrix_addresses_and_size[(table.x, table.y)],
                        bit_field_compressor_executable_path,
                        bit_field_sorter_executable_path, threshold_percentage)

                    self._load_usable_sdram(
                        matrix_addresses_and_size[(table.x, table.y)], table.x,
                        table.y, transceiver, routing_table_compressor_app_id,
                        cores)

                    self._load_compressor_data(
                        table.x, table.y, time_per_iteration, transceiver,
                        bit_field_compressor_executable_path, cores,
                        compress_only_when_needed,
                        compress_as_much_as_possible)
                except CantFindSDRAMToUseException:
                    run_by_host.append((table.x, table.y))

        return run_by_host

    @staticmethod
    def _convert_to_microseconds(seconds):
        return seconds * SECOND_TO_MICRO_SECOND

    def _load_compressor_data(
            self, chip_x, chip_y, time_per_iteration, transceiver,
            bit_field_compressor_executable_path, cores,
            compress_only_when_needed, compress_as_much_as_possible):
        """ updates the user1 address for the compressor cores so they can \
        set the time per attempt

        :param chip_x: chip x coord
        :param chip_y: chip y coord
        :param time_per_iteration: time per attempt of compression
        :param transceiver: SpiNNMan instance
        :param bit_field_compressor_executable_path: path for the compressor \
        binary
        :param compress_only_when_needed: bool flag asking if compress only \
        when needed
        :param compress_as_much_as_possible: bool flag asking if should \
        compress as much as possible
        :param cores: the executable targets
        :rtype: None
        """
        compressor_cores = cores.get_cores_for_binary(
            bit_field_compressor_executable_path)
        for processor_id in compressor_cores.get_core_subset_for_chip(
                chip_x, chip_y).processor_ids:
            user1_base_address = \
                transceiver.get_user_1_register_address_from_core(processor_id)
            user2_base_address = \
                transceiver.get_user_2_register_address_from_core(processor_id)
            user3_base_address = \
                transceiver.get_user_3_register_address_from_core(processor_id)
            transceiver.write_memory(
                chip_x, chip_y, user1_base_address,
                self._ONE_WORDS.pack(
                    self._convert_to_microseconds(time_per_iteration)),
                self._USER_BYTES)
            transceiver.write_memory(
                chip_x, chip_y, user2_base_address,
                self._ONE_WORDS.pack(compress_only_when_needed),
                self._USER_BYTES)
            transceiver.write_memory(
                chip_x, chip_y, user3_base_address,
                self._ONE_WORDS.pack(compress_as_much_as_possible),
                self._USER_BYTES)

    def _load_usable_sdram(
            self, matrix_addresses_and_size, chip_x, chip_y, transceiver,
            routing_table_compressor_app_id, cores):
        """ loads the addresses of stealable sdram

        :param matrix_addresses_and_size: sdram usable and sizes
        :param chip_x: the chip x to consider here
        :param chip_y: the chip y to consider here
        :param transceiver: the spinnman instance
        :param routing_table_compressor_app_id: system app id.
        :param cores: the cores that compressor will run on
        :rtype: None
        """
        address_data = \
            self._generate_chip_matrix_data(matrix_addresses_and_size)

        # get sdram address on chip
        try:
            sdram_address = transceiver.malloc_sdram(
                chip_x, chip_y, len(address_data),
                routing_table_compressor_app_id)
        except (SpinnmanInvalidParameterException,
                SpinnmanUnexpectedResponseCodeException):
            sdram_address = self._steal_from_matrix_addresses(
                matrix_addresses_and_size, len(address_data))
            address_data = \
                self._generate_chip_matrix_data(matrix_addresses_and_size)

        # write sdram
        transceiver.write_memory(
            chip_x, chip_y, sdram_address, address_data, len(address_data))

        # get the only processor on the chip
        processor_id = list(cores.all_core_subsets.get_core_subset_for_chip(
            chip_x, chip_y).processor_ids)[0]

        # update user 2 with location
        user_3_base_address = \
            transceiver.get_user_3_register_address_from_core(processor_id)
        transceiver.write_memory(
            chip_x, chip_y, user_3_base_address,
            self._ONE_WORDS.pack(sdram_address), self._USER_BYTES)

    def _generate_chip_matrix_data(self, list_of_sizes_and_address):
        """ generate the data for the chip matrix data

        :param list_of_sizes_and_address: list of sdram addresses and sizes
        :return: byte array of data
        """
        data = b""
        data += self._ONE_WORDS.pack(len(list_of_sizes_and_address))
        for (memory_address, size) in list_of_sizes_and_address:
            data += self._TWO_WORDS.pack(memory_address, size)
        return data

    def _load_address_data(
            self, addresses, chip_x, chip_y, transceiver,
            routing_table_compressor_app_id, cores, matrix_addresses_and_size,
            bit_field_compressor_executable_path,
            bit_field_sorter_executable_path, threshold_percentage):
        """ loads the bitfield addresses space

        :param addresses: the addresses to load
        :param chip_x: the chip x to consider here
        :param chip_y: the chip y to consider here
        :param transceiver: the spinnman instance
        :param routing_table_compressor_app_id: system app id.
        :param cores: the cores that compressor will run on
        :param bit_field_compressor_executable_path: the path to the \
        compressor binary path
        :param bit_field_sorter_executable_path: the path to the sorter binary
        :rtype: None
        """
        # generate address_data
        address_data = self._generate_chip_data(
            addresses[(chip_x, chip_y)],
            cores.get_cores_for_binary(
                bit_field_compressor_executable_path).get_core_subset_for_chip(
                    chip_x, chip_y),
            threshold_percentage)

        # get sdram address on chip
        try:
            sdram_address = transceiver.malloc_sdram(
                chip_x, chip_y, len(address_data),
                routing_table_compressor_app_id)
        except (SpinnmanInvalidParameterException,
                SpinnmanUnexpectedResponseCodeException):
            sdram_address = self._steal_from_matrix_addresses(
                matrix_addresses_and_size, len(address_data))

        # write sdram
        transceiver.write_memory(
            chip_x, chip_y, sdram_address, address_data, len(address_data))

        # get the only processor on the chip
        sorter_cores = cores.get_cores_for_binary(
            bit_field_sorter_executable_path)
        processor_id = list(sorter_cores.get_core_subset_for_chip(
            chip_x, chip_y).processor_ids)[0]

        # update user 2 with location
        user_2_base_address = \
            transceiver.get_user_2_register_address_from_core(processor_id)
        transceiver.write_memory(
            chip_x, chip_y, user_2_base_address,
            self._ONE_WORDS.pack(sdram_address), self._USER_BYTES)

    def _load_routing_table_data(
            self, table, app_id, transceiver,
            routing_table_compressor_app_id, progress_bar, cores,
            matrix_addresses_and_size):
        """ loads the routing table data

        :param table: the routing table to load
        :param app_id: application app id
        :param transceiver: spinnman instance
        :param progress_bar: progress bar
        :param routing_table_compressor_app_id: system app id
        :param cores: the cores that the compressor going to run on
        :rtype: None
        :raises CantFindSDRAMToUse when sdram is not malloc-ed or stolen
        """

        routing_table_data = self._build_routing_table_data(app_id, table)

        # go to spinnman and ask for a memory region of that size per chip.
        try:
            base_address = transceiver.malloc_sdram(
                table.x, table.y, len(routing_table_data),
                routing_table_compressor_app_id)
        except (SpinnmanInvalidParameterException,
                SpinnmanUnexpectedResponseCodeException):
            base_address = self._steal_from_matrix_addresses(
                matrix_addresses_and_size, len(routing_table_data))

        # write SDRAM requirements per chip
        transceiver.write_memory(
            table.x, table.y, base_address, routing_table_data)

        # get the only processor on the chip
        processor_id = list(cores.all_core_subsets.get_core_subset_for_chip(
            table.x, table.y).processor_ids)[0]

        # update user 1 with location
        user_1_base_address = \
            transceiver.get_user_1_register_address_from_core(processor_id)
        transceiver.write_memory(
            table.x, table.y, user_1_base_address,
            self._ONE_WORDS.pack(base_address), self._USER_BYTES)

        # update progress bar
        progress_bar.update()

    def _build_routing_table_data(self, app_id, routing_table):
        """ builds routing data as needed for the compressor cores

        :param app_id: appid of the application to load entries with
        :param routing_table: the uncompressed routing table
        :return: data array
        """
        data = b''
        data += self._TWO_WORDS.pack(app_id, routing_table.number_of_entries)

        # sort entries based on generality
        sorted_routing_table = sorted(
            routing_table.multicast_routing_entries,
            key=lambda rt_entry: ordered_covering_generality(
                rt_entry.routing_entry_key, rt_entry.mask))

        # write byte array for the sorted table
        for entry in sorted_routing_table:
            data += self._FOUR_WORDS.pack(
                entry.routing_entry_key, entry.mask,
                Router.convert_routing_table_entry_to_spinnaker_route(entry),
                Compression.make_source_hack(entry=entry))
        return bytearray(data)

    @staticmethod
    def _steal_from_matrix_addresses(matrix_addresses_and_size, size_to_steal):
        """ steals memory from synaptic matrix as needed

        :param matrix_addresses_and_size: matrix addresses and sizes
        :param size_to_steal: size needed to steal from matrix's.
        :return: address to start steal from
        :raises CantFindSDRAMToUseException: when no space is big enough to /
        steal from.
        """
        for pos, (base_address, size) in enumerate(matrix_addresses_and_size):
            if size >= size_to_steal:
                new_size = size - size_to_steal
                matrix_addresses_and_size[pos] = (base_address, new_size)
                return base_address
        raise CantFindSDRAMToUseException()

    def _add_to_addresses(
            self, vertex, placement, transceiver, region_addresses,
            sdram_block_addresses_and_sizes):
        """ adds data about the api based vertex.

        :param vertex: vertex which utilises the api
        :param placement: placement of vertex
        :param transceiver:  spinnman instance
        :param region_addresses: store for data regions
        :param sdram_block_addresses_and_sizes: store for surplus sdram.
        :rtype: None
        """

        # store the region sdram address's
        bit_field_sdram_address = vertex.bit_field_base_address(
            transceiver, placement)
        key_to_atom_map = vertex.key_to_atom_map_region_base_address(
            transceiver, placement)
        region_addresses[placement.x, placement.y].append(
            (bit_field_sdram_address, key_to_atom_map, placement.p))

        # store the available space from the matrix to steal
        blocks = vertex.regeneratable_sdram_blocks_and_sizes(
            transceiver, placement)

        for (address, size) in blocks:
            if size != 0 and size > self._MIN_SIZE_FOR_HEAP:
                sdram_block_addresses_and_sizes[
                    placement.x, placement.y].append((address, size))
        sorted(
            sdram_block_addresses_and_sizes[placement.x, placement.y],
            key=lambda data: data[0])

    def _generate_addresses(
            self, machine_graph, placements, transceiver, progress_bar,
            graph_mapper):
        """ generates the bitfield sdram addresses

        :param machine_graph: machine graph
        :param placements: placements
        :param transceiver: spinnman instance
        :param progress_bar: the progress bar
        :param: graph_mapper: mapping between graphs
        :return: region_addresses and the executable targets to load the \
        router table compressor with bitfield. and the executable path and \
        the synaptic matrix spaces to corrupt
        """

        # data holders
        region_addresses = defaultdict(list)
        sdram_block_addresses_and_sizes = defaultdict(list)

        for machine_vertex in progress_bar.over(
                machine_graph.vertices, finish_at_end=False):
            placement = placements.get_placement_of_vertex(machine_vertex)

            # locate the interface vertex (maybe app or machine)
            vertex = \
                HostBasedBitFieldRouterCompressor.locate_vertex_with_the_api(
                    machine_vertex, graph_mapper)
            if vertex is not None:
                self._add_to_addresses(
                        vertex, placement, transceiver, region_addresses,
                        sdram_block_addresses_and_sizes)

        return region_addresses, sdram_block_addresses_and_sizes

    def _generate_chip_data(self, address_list, cores, threshold_percentage):
        """ generate byte array data for a list of sdram addresses and \
        finally the time to run per compression iteration

        :param address_list: the list of sdram addresses
        :param cores: compressor cores on this chip.
        :return: the byte array
        """
        data = b""
        data += self._ONE_WORDS.pack(threshold_percentage)
        data += self._ONE_WORDS.pack(len(address_list))
        for (bit_field, key_to_atom, processor_id) in address_list:
            data += self._THREE_WORDS.pack(
                bit_field, key_to_atom, processor_id)
        data += self._ONE_WORDS.pack(len(cores))
        compression_cores = list(cores.processor_ids)
        data += struct.pack("<{}I".format(len(cores)), *compression_cores)
        return data
