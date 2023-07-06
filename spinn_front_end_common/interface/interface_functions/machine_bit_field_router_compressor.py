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

import functools
import logging
import struct
from typing import Dict, List, Sequence, Tuple
from typing_extensions import NewType
from collections import defaultdict
from spinn_utilities.config_holder import get_config_bool, get_config_int
from spinn_utilities.log import FormatAdapter
from spinn_utilities.progress_bar import ProgressBar
from spinn_machine import CoreSubsets, Router, Chip, CoreSubset
from spinnman.exceptions import (
    SpinnmanInvalidParameterException,
    SpinnmanUnexpectedResponseCodeException, SpiNNManCoresNotInStateException)
from spinnman.model import ExecutableTargets
from spinnman.model.enums import CPUState, ExecutableType
from pacman.model.placements import Placement
from pacman.model.routing_tables import (
    MulticastRoutingTables, AbstractMulticastRoutingTable)
from pacman.operations.router_compressors.ordered_covering_router_compressor\
    import get_generality as generality
from spinn_front_end_common.abstract_models import (
    AbstractSupportsBitFieldRoutingCompression)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.report_functions.\
    bit_field_compressor_report import (
        generate_provenance_item)
from spinn_front_end_common.utilities.exceptions import (
    CantFindSDRAMToUseException)
from spinn_front_end_common.utilities.helpful_functions import (
    get_defaultable_source_id, n_word_struct)
from spinn_front_end_common.utilities.system_control_logic import (
    run_system_application)
from spinn_front_end_common.utilities.constants import (
    BIT_FIELD_COMMS_SDRAM_TAG, BIT_FIELD_USABLE_SDRAM_TAG,
    BIT_FIELD_ADDRESSES_SDRAM_TAG, BIT_FIELD_ROUTING_TABLE_SDRAM_TAG)
from .load_executable_images import filter_targets
from .host_bit_field_router_compressor import (
    generate_key_to_atom_map, generate_report_path,
    HostBasedBitFieldRouterCompressor)

# Special types to stop these two from getting mixed up and reduce my confusion
#: An address of a piece of memory (SDRAM?) and its size
_RamChunk = NewType("_RamChunk", Tuple[int, int])
#: An address and the core to which it is assigned
_RamAssignment = NewType("_RamAssignment", Tuple[int, int])

logger = FormatAdapter(logging.getLogger(__name__))

#: Size of SDRAM allocation for addresses
SIZE_OF_SDRAM_ADDRESS_IN_BYTES = (17 * 2 * 4) + (3 * 4)

# 7 pointers or int for each core. 4 Bytes for each  18 cores max
SIZE_OF_COMMS_SDRAM = 7 * 4 * 18

SECOND_TO_MICRO_SECOND = 1000000


class _MachineBitFieldRouterCompressor(object):
    """
    On-machine bitfield-aware routing table compression.
    """
    __slots__ = (
        "_compressor_aplx", "_compressor_type", "__txrx", "__app_id",
        "__compress_max",
        # Configuration parameters
        "_time_per_iteration", "_threshold_percentage", "_retry_count",
        "_report_iobuf", "_write_report")

    #: SDRAM tag the router compressor expects to find there routing tables in
    ROUTING_TABLE_SDRAM_TAG = 1

    #: SDRAM tag for the addresses the router compressor expects to find the
    #: bitfield addresses for the chip.
    BIT_FIELD_ADDRESSES_SDRAM_TAG = 2

    #
    TIMES_CYCLED_ROUTING_TABLES = 3

    #: the successful identifier
    SUCCESS = 0

    #: How many header elements are in the region addresses (1, n addresses)
    N_REGIONS_ELEMENT = 1

    #: Minimum size a heap object needs in SDRAM. (limit on the size of useful
    #: SDRAM regions to borrow)
    _MIN_SIZE_FOR_HEAP = 32

    # bit offset for compress only when needed
    _ONLY_WHEN_NEEDED_BIT_OFFSET = 1

    # bit offset for compress as much as possible
    _AS_MUCH_AS_POSS_BIT_OFFSET = 2

    # structs for performance requirements.
    _FOUR_WORDS = struct.Struct("<IIII")
    _TWO_WORDS = struct.Struct("<II")
    _ONE_WORD = struct.Struct("<I")

    # binary names
    _BIT_FIELD_SORTER_AND_SEARCH_EXECUTOR_APLX = \
        "bit_field_sorter_and_searcher.aplx"

    _HOST_BAR_TEXT = \
        "on host compressing routing tables and merging in bitfields as " \
        "appropriate"
    _ON_CHIP_ERROR_MESSAGE = \
        "The router compressor with bit field on {}:{} failed to complete. " \
        "Will execute host based routing compression instead"
    _ON_HOST_WARNING_MESSAGE = \
        "Will be executing compression for {} chips on the host, as they " \
        "failed to complete when running on chip"

    def __init__(
            self, compressor_aplx: str, compressor_type: str,
            compress_as_much_as_possible: bool = False):
        """
        :param str compressor_aplx:
        :param str compressor_type:
        :param bool compress_as_much_as_possible:
            whether to compress as much as possible
        """
        self._compressor_aplx = compressor_aplx
        self._compressor_type = compressor_type
        self.__txrx = FecDataView.get_transceiver()
        self.__app_id = FecDataView.get_app_id()
        self.__compress_max = compress_as_much_as_possible
        # Read the config once
        self._time_per_iteration = get_config_int(
            "Mapping",
            "router_table_compression_with_bit_field_iteration_time") or 1000
        self._threshold_percentage = get_config_int(
            "Mapping",
            "router_table_compression_with_bit_field_acceptance_threshold")
        self._retry_count = get_config_int(
            "Mapping", "router_table_compression_with_bit_field_retry_count")
        self._report_iobuf = get_config_bool(
            "Reports", "write_compressor_iobuf") or False
        self._write_report = get_config_bool(
            "Reports", "write_router_compression_with_bitfield_report")

    def compress(self) -> ExecutableTargets:
        """
        Entrance for routing table compression with bit field.

        :return: where the compressors ran
        :rtype: ~spinnman.model.ExecutableTargets
        """
        view = FecDataView()
        routing_tables = FecDataView.get_uncompressed()
        if len(routing_tables.routing_tables) == 0:
            return ExecutableTargets()

        # new app id for this simulation
        compressor_app_id = view.get_new_id()

        text = f"On chip {self._compressor_type} compressor with bitfields"

        if self._retry_count is not None:
            text += f" capped at {self._retry_count} retries"
        progress_bar = ProgressBar(
            total_number_of_things_to_do=(
                FecDataView.get_n_vertices() +
                (len(routing_tables.routing_tables) *
                 self.TIMES_CYCLED_ROUTING_TABLES)),
            string_describing_what_being_progressed=text)

        # locate data and on_chip_cores to load binary on
        addresses, matrix_addresses_and_size = self._generate_addresses(
            progress_bar)

        # create executable targets
        (compressor_executable_targets, sorter_executable_path,
         compressor_executable_path) = self._generate_core_subsets(
            routing_tables, progress_bar)

        # load data into sdram
        on_host_chips = self._load_data(
            addresses, compressor_app_id, routing_tables, progress_bar,
            compressor_executable_targets,
            matrix_addresses_and_size, compressor_executable_path,
            sorter_executable_path)

        # load and run binaries
        try:
            run_system_application(
                compressor_executable_targets, compressor_app_id,
                self._report_iobuf,
                functools.partial(
                    self._check_bit_field_router_compressor_for_success,
                    host_chips=on_host_chips,
                    sorter_binary_path=sorter_executable_path),
                frozenset([CPUState.FINISHED]), True,
                "bit_field_compressor_on_{}_{}_{}.txt",
                [sorter_executable_path], progress_bar,
                logger=logger)
        except SpiNNManCoresNotInStateException as e:
            logger.exception(e.failed_core_states().get_status_string())
            try:
                self.__txrx.stop_application(compressor_app_id)
            except Exception:  # pylint: disable=broad-except
                logger.warning("Could not stop compressor!")
            raise e

        # start the host side compressions if needed
        if on_host_chips:
            self._on_host_compress(on_host_chips, routing_tables)

        return compressor_executable_targets

    def _on_host_compress(
            self, on_host_chips: Sequence[Chip],
            routing_tables: MulticastRoutingTables):
        """
        :param iterable(Chip) on_host_chips:
        :param MulticastRoutingTables routing_tables:
        """
        if self._write_report:
            report_folder_path = generate_report_path()
        else:
            report_folder_path = None

        most_costly_cores: Dict[Chip, Dict[int, int]] = defaultdict(
            lambda: defaultdict(int))
        for partition in FecDataView.iterate_partitions():
            for edge in partition.edges:
                sttr = edge.pre_vertex.splitter
                for vertex in sttr.get_source_specific_in_coming_vertices(
                        partition.pre_vertex, partition.identifier):
                    place = FecDataView.get_placement_of_vertex(vertex)
                    if place.chip in on_host_chips:
                        most_costly_cores[place.chip][place.p] += 1
        logger.warning(self._ON_HOST_WARNING_MESSAGE, len(on_host_chips))

        with ProgressBar(len(on_host_chips), self._HOST_BAR_TEXT) as progress:
            compressed_tables = MulticastRoutingTables()
            key_atom_map = generate_key_to_atom_map()

            compressor = HostBasedBitFieldRouterCompressor(
                key_atom_map, report_folder_path, most_costly_cores)
            for chip in progress.over(on_host_chips, False):
                table = routing_tables.get_routing_table_for_chip(
                    chip.x, chip.y)
                if table:
                    compressor.compress_bitfields(table, compressed_tables)

            # load host compressed routing tables
            for table in compressed_tables.routing_tables:
                if table.multicast_routing_entries:
                    self.__txrx.clear_multicast_routes(table.x, table.y)
                    self.__txrx.load_multicast_routes(
                        table.x, table.y, table.multicast_routing_entries,
                        app_id=self.__app_id)

    def _generate_core_subsets(
            self, routing_tables: MulticastRoutingTables,
            progress_bar: ProgressBar) -> Tuple[ExecutableTargets, str, str]:
        """
        Generates the core subsets for the binaries.

        :param ~.MulticastRoutingTables routing_tables: the routing tables
        :param ~.ProgressBar progress_bar: progress bar
        :param ~spinnman.model.ExecutableTargets system_executable_targets:
            the executables targets to cores
        :return: (targets, sorter path, and compressor path)
        :rtype: tuple(~spinnman.model.ExecutableTargets, str, str)
        """
        sorter_cores = CoreSubsets()
        compressor_cores = CoreSubsets()

        sys_cores = filter_targets(lambda ty: ty is ExecutableType.SYSTEM)
        for table in progress_bar.over(routing_tables, False):
            # add 1 core to the sorter, and the rest to compressors
            sorter = None
            for processor in table.chip.processors:
                # The monitor is not for our use
                if processor.is_monitor:
                    continue
                # Our system cores are also already busy
                if sys_cores.all_core_subsets.is_core(
                        table.x, table.y, processor.processor_id):
                    continue
                # Can run on this core
                if sorter is None:
                    sorter = processor
                    sorter_cores.add_processor(
                        table.x, table.y, processor.processor_id)
                else:
                    compressor_cores.add_processor(
                        table.x, table.y, processor.processor_id)

        # convert core subsets into executable targets
        executable_targets = ExecutableTargets()

        # bit field executable paths
        sorter_aplx = FecDataView.get_executable_path(
            self._BIT_FIELD_SORTER_AND_SEARCH_EXECUTOR_APLX)
        compressor_aplx = FecDataView.get_executable_path(
            self._compressor_aplx)

        # add the sets
        executable_targets.add_subsets(
            sorter_aplx, sorter_cores, ExecutableType.SYSTEM)
        executable_targets.add_subsets(
            compressor_aplx, compressor_cores, ExecutableType.SYSTEM)

        return (executable_targets, sorter_aplx, compressor_aplx)

    def _check_bit_field_router_compressor_for_success(
            self, executable_targets: ExecutableTargets,
            host_chips: List[Chip], sorter_binary_path: str) -> bool:
        """
        Goes through the cores checking for cores that have failed to
        generate the compressed routing tables with bitfield.

        :param ~spinnman.model.ExecutableTargets executable_targets:
            cores to load router compressor with bitfield on
        :param list(Chip) host_chips:
            the chips which need to be ran on host.
        :param str sorter_binary_path: the path to the sorter binary
        :rtype: bool
        """
        transceiver = FecDataView.get_transceiver()
        sorter_cores = executable_targets.get_cores_for_binary(
            sorter_binary_path)
        success = True
        for core_subset in sorter_cores:
            x, y = core_subset.x, core_subset.y
            for p in core_subset.processor_ids:
                # Read the result from USER1/USER2 registers
                result = transceiver.read_user(x, y, p, 1)
                bit_fields_merged = transceiver.read_user(x, y, p, 2)

                if result != self.SUCCESS:
                    host_chips.append(FecDataView.get_chip_at(x, y))
                    success = False
                generate_provenance_item(x, y, bit_fields_merged)
        return success

    def _load_data(
            self, addresses: Dict[Chip, List[_RamAssignment]],
            compressor_app_id: int, routing_tables: MulticastRoutingTables,
            progress_bar: ProgressBar, cores: ExecutableTargets,
            matrix_addresses_and_size: Dict[Chip, List[_RamChunk]],
            compressor_executable_path: str,
            sorter_executable_path: str) -> List[Chip]:
        """
        load all data onto the chip.

        :param dict(Chip,tuple(int,int)) addresses:
            the addresses for bitfields in SDRAM
        :param compressor_app_id:
            the app_id for the system application
        :param ~.MulticastRoutingTables routing_tables:
            the routing tables
        :param ~.ProgressBar progress_bar: progress bar
        :param ~spinnman.model.ExecutableTargets cores:
            the cores that compressor will run on
        :param dict(Chip,tuple(int,int)) matrix_addresses_and_size:
            maps chips to regeneration SDRAM and size for exploitation
        :param str compressor_executable_path:
            the path to the compressor binary path
        :param str sorter_executable_path:
            the path to the sorter binary
        :return:
            the list of which chips will need to use host compression,
            as the malloc failed.
        :rtype: list(~spinn_machine.Chip)
        """
        run_by_host = list()
        for table in routing_tables.routing_tables:
            chip = table.chip
            borrowable_spaces = matrix_addresses_and_size[chip]
            try:
                self._load_routing_table_data(
                    table, compressor_app_id, cores, borrowable_spaces)

                # update progress bar
                progress_bar.update()

                comms_sdram = self.__txrx.malloc_sdram(
                    table.x, table.y, SIZE_OF_COMMS_SDRAM, compressor_app_id,
                    BIT_FIELD_COMMS_SDRAM_TAG)

                self._load_address_data(
                    addresses, chip, compressor_app_id, cores,
                    borrowable_spaces, compressor_executable_path,
                    sorter_executable_path, comms_sdram)

                self._load_usable_sdram(
                    borrowable_spaces, chip, compressor_app_id, cores)

                self._load_compressor_data(
                    chip, compressor_executable_path, cores, comms_sdram)
            except CantFindSDRAMToUseException:
                run_by_host.append(chip)

        return run_by_host

    def _load_compressor_data(
            self, chip: Chip, compressor_executable_path: str,
            cores: ExecutableTargets, comms_sdram: int):
        """
        Updates the user addresses for the compressor cores with the
        compression settings.

        :param int chip: chip to load on
        :param str compressor_executable_path:
            path for the compressor binary
        :param ~spinnman.model.ExecutableTargets cores: the executable targets
        :param int comms_sdram: Address for communications block
        """
        chip_x, chip_y = chip.x, chip.y
        compressor_cores = cores.get_cores_for_binary(
            compressor_executable_path)
        for processor_id in compressor_cores.get_core_subset_for_chip(
                chip_x, chip_y).processor_ids:
            # user 1 the time per compression attempt
            time_per_iteration = get_config_int(
                "Mapping",
                "router_table_compression_with_bit_field_iteration_time")
            self.__txrx.write_user(
                chip_x, chip_y, processor_id, 1,
                int(time_per_iteration * SECOND_TO_MICRO_SECOND))
            # user 2 Compress as much as needed flag
            self.__txrx.write_user(
                chip_x, chip_y, processor_id, 2, self.__compress_max)
            # user 3 the comms_sdram area
            self.__txrx.write_user(
                chip_x, chip_y, processor_id, 3, comms_sdram)

    def _load_usable_sdram(
            self, sizes_and_address: List[_RamChunk],
            chip: Chip, compressor_app_id: int, cores: ExecutableTargets):
        """
        loads the addresses of borrowable SDRAM.

        :param list(tuple(int,int)) sizes_and_address:
            SDRAM usable and sizes for the chip
        :param Chip chip: the chip to consider here
        :param int compressor_app_id: system app_id
        :param ~spinnman.model.ExecutableTargets cores:
            the cores that compressor will run on
        """
        address_data = self._generate_chip_matrix_data(sizes_and_address)

        # get sdram address on chip
        try:
            sdram_address = self.__txrx.malloc_sdram(
                chip.x, chip.y, len(address_data), compressor_app_id,
                BIT_FIELD_USABLE_SDRAM_TAG)
        except (SpinnmanInvalidParameterException,
                SpinnmanUnexpectedResponseCodeException):
            sdram_address = self._borrow_from_matrix_addresses(
                sizes_and_address, len(address_data))
            address_data = self._generate_chip_matrix_data(sizes_and_address)

        # write sdram
        self.__txrx.write_memory(chip.x, chip.y, sdram_address, address_data)

        # tell the compressor where the SDRAM is
        for p in cores.all_core_subsets.get_core_subset_for_chip(
                chip.x, chip.y).processor_ids:
            # update user 3 with location
            self.__txrx.write_user(chip.x, chip.y, p, 3, sdram_address)

    def _generate_chip_matrix_data(
            self, borrowable_spaces: List[_RamChunk]) -> bytes:
        """
        Generate the data for the chip matrix data.

        :param list(tuple(int,int)) borrowable_spaces:
            SDRAM addresses and sizes
        :return: byte array of data
        :rtype: bytes
        """
        data = bytearray(
            self._ONE_WORD.size +
            len(borrowable_spaces) * self._TWO_WORDS.size)
        offset = 0
        self._ONE_WORD.pack_into(data, offset, len(borrowable_spaces))
        offset += self._ONE_WORD.size
        for (memory_address, size) in borrowable_spaces:
            self._TWO_WORDS.pack_into(data, offset, memory_address, size)
            offset += self._TWO_WORDS.size
        return bytes(data)

    def _load_address_data(
            self, region_addresses: Dict[Chip, List[_RamAssignment]],
            chip: Chip, compressor_app_id: int, cores: ExecutableTargets,
            borrowable_spaces: List[_RamChunk],
            compressor_executable_path: str,
            sorter_executable_path: str, comms_sdram: int):
        """
        loads the bitfield region_addresses space.

        :param dict(Chip,tuple(int,int)) region_addresses:
            the addresses to load
        :param int chip: the chip to consider here
        :param int compressor_app_id: system app_id.
        :param ~spinnman.model.ExecutableTargets cores:
            the cores that compressor will run on
        :param borrowable_spaces:
            Where space can be borrowed from
        :param str compressor_executable_path:
            the path to the compressor binary path
        :param str sorter_executable_path:
            the path to the sorter binary
        :param int comms_sdram: Address for communications block
        """
        # generate address_data
        address_data = self._generate_chip_data(
            region_addresses[chip],
            cores.get_cores_for_binary(
                compressor_executable_path).get_core_subset_for_chip(
                    chip.x, chip.y),
            comms_sdram)

        # get sdram address on chip
        try:
            sdram_address = self.__txrx.malloc_sdram(
                chip.x, chip.y, len(address_data), compressor_app_id,
                BIT_FIELD_ADDRESSES_SDRAM_TAG)
        except (SpinnmanInvalidParameterException,
                SpinnmanUnexpectedResponseCodeException):
            sdram_address = self._borrow_from_matrix_addresses(
                borrowable_spaces, len(address_data))

        # write sdram
        self.__txrx.write_memory(chip.x, chip.y, sdram_address, address_data)

        # get the only processor on the chip
        sorter_cores = cores.get_cores_for_binary(sorter_executable_path)
        processor_id = list(sorter_cores.get_core_subset_for_chip(
            chip.x, chip.y).processor_ids)[0]

        # update user 2 with location
        self.__txrx.write_user(
            chip.x, chip.y, processor_id, 2, sdram_address)

    def _load_routing_table_data(
            self, table: AbstractMulticastRoutingTable,
            compressor_app_id: int, cores: ExecutableTargets,
            borrowable_spaces: List[_RamChunk]):
        """
        loads the routing table data.

        :param table: the routing table to load
        :type table:
            ~pacman.model.routing_tables.AbstractMulticastRoutingTable
        :param int compressor_app_id: system app_id
        :param ~spinnman.model.ExecutableTargets cores:
            the cores that the compressor going to run on
        :param borrowable_spaces: Where we can borrow memory from
        :raises CantFindSDRAMToUse: when SDRAM is not malloc'ed or stolen
        """
        routing_table_data = self._build_routing_table_data(
            self.__app_id, table)

        # go to spinnman and ask for a memory region of that size per chip.
        try:
            base_address = self.__txrx.malloc_sdram(
                table.x, table.y, len(routing_table_data), compressor_app_id,
                BIT_FIELD_ROUTING_TABLE_SDRAM_TAG)
        except (SpinnmanInvalidParameterException,
                SpinnmanUnexpectedResponseCodeException):
            base_address = self._borrow_from_matrix_addresses(
                borrowable_spaces, len(routing_table_data))

        # write SDRAM requirements per chip
        self.__txrx.write_memory(
            table.x, table.y, base_address, routing_table_data)

        # Tell the compressor where the SDRAM is
        for p in cores.all_core_subsets.get_core_subset_for_chip(
                table.x, table.y).processor_ids:
            self.__txrx.write_user(table.x, table.y, p, 1, base_address)

    def _build_routing_table_data(
            self, app_id: int,
            routing_table: AbstractMulticastRoutingTable) -> bytes:
        """
        Builds routing data as needed for the compressor cores.

        :param int app_id: app_id of the application to load entries with
        :param ~.AbstractMulticastRoutingTable routing_table:
            the uncompressed routing table
        :return: data array
        :rtype: bytearray
        """
        data = self._TWO_WORDS.pack(app_id, routing_table.number_of_entries)

        # sort entries based on generality
        sorted_routing_table = sorted(
            routing_table.multicast_routing_entries,
            key=lambda rt_entry: generality(
                rt_entry.routing_entry_key, rt_entry.mask))

        # write byte array for the sorted table
        for entry in sorted_routing_table:
            data += self._FOUR_WORDS.pack(
                entry.routing_entry_key, entry.mask,
                Router.convert_routing_table_entry_to_spinnaker_route(entry),
                get_defaultable_source_id(entry=entry))
        return bytes(data)

    @staticmethod
    def _borrow_from_matrix_addresses(
            borrowable_spaces: List[_RamChunk], size_to_borrow: int) -> int:
        """
        Borrows memory from synaptic matrix as needed.

        :param list(tuple(int,int)) borrowable_spaces:
            matrix addresses and sizes of particular chip;
            updated by this method
        :param int size_to_borrow: size needed to borrow from matrices.
        :return: address to start borrow from
        :rtype: int
        :raises CantFindSDRAMToUseException:
            when no space is big enough to borrow from.
        """
        for pos, (base_address, size) in enumerate(borrowable_spaces):
            if size >= size_to_borrow:
                new_size = size - size_to_borrow
                borrowable_spaces[pos] = _RamChunk((base_address, new_size))
                return base_address
        raise CantFindSDRAMToUseException()

    def _add_to_addresses(
            self, vertex: AbstractSupportsBitFieldRoutingCompression,
            placement: Placement,
            region_addresses: Dict[Chip, List[_RamAssignment]],
            sdram_block_addresses_and_sizes: Dict[Chip, List[_RamChunk]]):
        """
        Adds data about the API-based vertex.

        :param AbstractSupportsBitFieldRoutingCompression vertex:
            vertex which utilises the API
        :param ~.Placement placement: placement of vertex
        :param dict(Chip,list(tuple(int,int))) region_addresses:
            store for data regions:
            maps chip to list of memory address and processor ID
        :param sdram_block_addresses_and_sizes:
            store for surplus SDRAM:
            maps chip to list of memory addresses and sizes
        :type sdram_block_addresses_and_sizes:
            dict(Chip,list(tuple(int,int)))
        """
        chip = placement.chip
        # store the region sdram address's
        bit_field_sdram_address = vertex.bit_field_base_address(placement)
        region_addresses[chip].append(
            _RamAssignment((bit_field_sdram_address, placement.p)))

        # store the available space from the matrix to borrow
        blocks = vertex.regeneratable_sdram_blocks_and_sizes(placement)

        for (address, size) in blocks:
            if size > self._MIN_SIZE_FOR_HEAP:
                sdram_block_addresses_and_sizes[chip].append(
                    _RamChunk((address, size)))
        sorted(
            sdram_block_addresses_and_sizes[chip],
            key=lambda data: data[0])

    def _generate_addresses(self, progress_bar: ProgressBar) -> Tuple[
            Dict[Chip, List[_RamAssignment]], Dict[Chip, List[_RamChunk]]]:
        """
        Generates the bitfield SDRAM addresses.

        :param ~.ProgressBar progress_bar: the progress bar
        :return: region_addresses and the executable targets to load the
            router table compressor with bitfield. and the SDRAM blocks
            available for use on each core that we plan to use
        :rtype: tuple(dict(Chip,tuple(int,int)),
            dict(Chip,list(tuple(int,int))))
        """
        # data holders
        region_addresses: Dict[Chip, List[_RamAssignment]] = defaultdict(list)
        sdram_block_addresses_and_sizes: Dict[
            Chip, List[_RamChunk]] = defaultdict(list)

        for app_vertex in progress_bar.over(
                FecDataView.iterate_vertices(), finish_at_end=False):
            for m_vertex in app_vertex.machine_vertices:
                placement = FecDataView.get_placement_of_vertex(m_vertex)
                if isinstance(
                        m_vertex, AbstractSupportsBitFieldRoutingCompression):
                    self._add_to_addresses(
                        m_vertex, placement, region_addresses,
                        sdram_block_addresses_and_sizes)
        return region_addresses, sdram_block_addresses_and_sizes

    def _generate_chip_data(
            self, address_list: List[_RamAssignment],
            cores: CoreSubset, comms_sdram: int) -> bytes:
        """
        Generate the region_addresses_t data.

        * Minimum percentage of bitfields to be merge in (currently ignored)

        * Number of times that the sorters should set of the compressions again

        * Pointer to the area malloc'ed to hold the comms_sdram

        * Number of processors in the list

        * The data for the processors

        :param list(tuple(int,int)) address_list:
            the list of SDRAM addresses
        :param ~.CoreSubset cores: compressor cores on this chip.
        :param int comms_sdram: Address for communications block
        :return: the byte array
        :rtype: bytes
        """
        data = bytearray(
            self._FOUR_WORDS.size +
            self._TWO_WORDS.size * len(address_list) +
            self._ONE_WORD.size * (1 + len(cores)))
        offset = 0
        self._FOUR_WORDS.pack_into(
            data, offset, self._threshold_percentage,
            self._retry_count if self._retry_count is not None else 0xFFFFFFFF,
            comms_sdram, len(address_list))
        offset += self._FOUR_WORDS.size
        for (bit_field, processor_id) in address_list:
            self._TWO_WORDS.pack_into(data, offset, bit_field, processor_id)
            offset += self._TWO_WORDS.size
        self._ONE_WORD.pack_into(data, offset, len(cores))
        offset += self._ONE_WORD.size
        n_word_struct(len(cores)).pack_into(
            data, offset, *list(cores.processor_ids))
        return bytes(data)


def machine_bit_field_ordered_covering_compressor(
        compress_as_much_as_possible: bool = False) -> ExecutableTargets:
    """
    Compression with bit field and ordered covering.

    :param bool compress_as_much_as_possible:
        whether to compress as much as possible
    :return: where the compressors ran
    :rtype: ~spinnman.model.ExecutableTargets
    """
    compressor = _MachineBitFieldRouterCompressor(
        "bit_field_ordered_covering_compressor.aplx", "OrderedCovering",
        compress_as_much_as_possible)
    return compressor.compress()


def machine_bit_field_pair_router_compressor(
        compress_as_much_as_possible: bool = False) -> ExecutableTargets:
    """
    Compression with bit field pairing.

    :param bool compress_as_much_as_possible:
        whether to compress as much as possible
    :return: where the compressors ran
    :rtype: ~spinnman.model.ExecutableTargets
    """
    compressor = _MachineBitFieldRouterCompressor(
        "bit_field_pair_compressor.aplx", "Pair", compress_as_much_as_possible)
    return compressor.compress()
