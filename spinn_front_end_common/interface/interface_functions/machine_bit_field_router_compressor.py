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
from six import add_metaclass
from spinn_utilities.abstract_base import AbstractBase, abstractproperty
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spinn_utilities.progress_bar import ProgressBar
from spinn_machine import CoreSubsets, Router
from spinnman.exceptions import (
    SpinnmanInvalidParameterException,
    SpinnmanUnexpectedResponseCodeException, SpiNNManCoresNotInStateException)
from spinnman.model import ExecutableTargets
from spinnman.model.enums import CPUState
from pacman.model.routing_tables import MulticastRoutingTables
from pacman.operations.router_compressors.mundys_router_compressor.\
    ordered_covering import (
        get_generality as
        ordered_covering_generality)
from spinn_front_end_common.abstract_models.\
    abstract_supports_bit_field_routing_compression import (
        AbstractSupportsBitFieldRoutingCompression)
from spinn_front_end_common.interface.interface_functions.\
    on_chip_router_table_compression import (
        make_source_hack)
from spinn_front_end_common.utilities.report_functions.\
    bit_field_compressor_report import generate_provenance_item
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utilities.exceptions import (
    CantFindSDRAMToUseException)
from spinn_front_end_common.utilities import system_control_logic
from .load_executable_images import LoadExecutableImages
from .host_bit_field_router_compressor import HostBasedBitFieldRouterCompressor

logger = FormatAdapter(logging.getLogger(__name__))

#: sdram allocation for addresses
SIZE_OF_SDRAM_ADDRESS_IN_BYTES = (17 * 2 * 4) + (3 * 4)

# 7 pointers or int for each core. 4 Bytes for each  18 cores max
SIZE_OF_COMMS_SDRAM = 7 * 4 * 18

SECOND_TO_MICRO_SECOND = 1000000


@add_metaclass(AbstractBase)
class MachineBitFieldRouterCompressor(object):
    """ On-machine bitfield-aware routing table compression.

    :param ~pacman.model.routing_tables.MulticastRoutingTables routing_tables:
        routing tables
    :param ~spinnman.transceiver.Transceiver transceiver: spinnman instance
    :param ~spinn_machine.Machine machine: spinnMachine instance
    :param int app_id: app id of the application
    :param str provenance_file_path: file path for prov data
    :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
        machine graph
    :param ~pacman.model.placements.Placements placements:
        placements on machine
    :param ExecutableFinder executable_finder: where are binaries are located
    :param bool write_compressor_iobuf: flag saying if read IOBUF
    :param bool produce_report:
    :param str default_report_folder:
    :param bool use_timer_cut_off:
    :param int machine_time_step:
    :param int time_scale_factor:
    :param int threshold_percentage: the percentage of bitfields to do on chip
        before its considered a success
    :param ~spinnman.model.ExecutableTargets executable_targets:
        the set of targets and executables
    :param bool compress_as_much_as_possible:
        whether to compress as much as possible
    :param list(ProvenanceDataItem) provenance_data_objects:
    :return: where the compressors ran, and the provenance they generated
    :rtype: tuple(~spinnman.model.ExecutableTargets, list(ProvenanceDataItem))
    """

    __slots__ = []

    #: sdram tag the router compressor expects to find there routing tables in
    ROUTING_TABLE_SDRAM_TAG = 1

    #: sdram tag for the addresses the router compressor expects to find the
    #: bitfield addresses for the chip.
    BIT_FIELD_ADDRESSES_SDRAM_TAG = 2

    #
    TIMES_CYCLED_ROUTING_TABLES = 3

    #: the successful identifier
    SUCCESS = 0

    #: how many header elements are in the region addresses (1, n addresses)
    N_REGIONS_ELEMENT = 1

    # the number of bytes needed to read the user 2 register
    _USER_BYTES = 4

    #: min size a heap object needs in sdram. (limit on the size of useful
    #: sdram regions to steal)
    _MIN_SIZE_FOR_HEAP = 32

    # bit offset for compress only when needed
    _ONLY_WHEN_NEEDED_BIT_OFFSET = 1

    # bit offset for compress as much as possible
    _AS_MUCH_AS_POSS_BIT_OFFSET = 2

    # structs for performance requirements.
    _FOUR_WORDS = struct.Struct("<IIII")

    _THREE_WORDS = struct.Struct("<III")

    _TWO_WORDS = struct.Struct("<II")

    _ONE_WORDS = struct.Struct("<I")

    # binary names
    _BIT_FIELD_SORTER_AND_SEARCH_EXECUTOR_APLX = \
        "bit_field_sorter_and_searcher.aplx"

    _PROGRESS_BAR_TEXT = \
        "on chip compressing routing tables and merging in bitfields as " \
        "appropriate"
    _HOST_BAR_TEXT = \
        "on host compressing routing tables and merging in bitfields as " \
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
            write_compressor_iobuf, produce_report, default_report_folder,
            target_length, routing_infos, time_to_try_for_each_iteration,
            use_timer_cut_off, machine_time_step, time_scale_factor,
            threshold_percentage, executable_targets,
            compress_as_much_as_possible=False, provenance_data_objects=None):
        """ entrance for routing table compression with bit field

        :param ~.MulticastRoutingTables routing_tables:
        :param ~.Transceiver transceiver:
        :param ~.Machine machine:
        :param int app_id:
        :param str provenance_file_path:
        :param ~.MachineGraph machine_graph:
        :param ~.Placements placements:
        :param ~.ExecutableFinder executable_finder:
        :param bool write_compressor_iobuf:
        :param bool produce_report:
        :param str default_report_folder:
        :param bool use_timer_cut_off:
        :param int machine_time_step:
        :param int time_scale_factor:
        :param int threshold_percentage:
        :param ~.ExecutableTargets executable_targets:
        :param bool compress_as_much_as_possible:
        :param list(ProvenanceDataItem) provenance_data_objects:
        :rtype: tuple(~.ExecutableTargets,list(ProvenanceDataItem))
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
            machine_graph, placements, transceiver, progress_bar)

        # create executable targets
        (compressor_executable_targets, bit_field_sorter_executable_path,
         bit_field_compressor_executable_path) = self._generate_core_subsets(
            routing_tables, executable_finder, machine, progress_bar,
            executable_targets)

        # load data into sdram
        on_host_chips = self._load_data(
            addresses, transceiver, routing_table_compressor_app_id,
            routing_tables, app_id, machine,
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
                write_compressor_iobuf,
                functools.partial(
                    self._check_bit_field_router_compressor_for_success,
                    host_chips=on_host_chips,
                    sorter_binary_path=bit_field_sorter_executable_path,
                    prov_data_items=prov_items),
                [CPUState.FINISHED], True,
                "bit_field_compressor_on_{}_{}_{}.txt",
                [bit_field_sorter_executable_path], progress_bar,
                logger=logger)
        except SpiNNManCoresNotInStateException as e:
            logger.exception(transceiver.get_core_status_string(
                e.failed_core_states()))
            raise e

        # start the host side compressions if needed
        if len(on_host_chips) != 0:
            logger.warning(self._ON_HOST_WARNING_MESSAGE, len(on_host_chips))
            progress_bar = ProgressBar(
                total_number_of_things_to_do=len(on_host_chips),
                string_describing_what_being_progressed=self._HOST_BAR_TEXT)
            host_compressor = HostBasedBitFieldRouterCompressor()
            compressed_pacman_router_tables = MulticastRoutingTables()

            key_atom_map = host_compressor.generate_key_to_atom_map(
                machine_graph, routing_infos)

            for (chip_x, chip_y) in progress_bar.over(on_host_chips, False):
                prov_items.append(
                    host_compressor.start_compression_selection_process(
                        router_table=routing_tables.get_routing_table_for_chip(
                            chip_x, chip_y),
                        produce_report=produce_report,
                        report_folder_path=host_compressor.generate_report_path(
                            default_report_folder),
                        transceiver=transceiver, machine_graph=machine_graph,
                        placements=placements, machine=machine,
                        target_length=target_length,
                        time_to_try_for_each_iteration=(
                            time_to_try_for_each_iteration),
                        use_timer_cut_off=use_timer_cut_off,
                        compressed_pacman_router_tables=(
                            compressed_pacman_router_tables),
                        key_atom_map=key_atom_map))

            # load host compressed routing tables
            for table in compressed_pacman_router_tables.routing_tables:
                if (not machine.get_chip_at(table.x, table.y).virtual
                        and table.multicast_routing_entries):
                    transceiver.clear_multicast_routes(table.x, table.y)
                    transceiver.load_multicast_routes(
                        table.x, table.y, table.multicast_routing_entries,
                        app_id=app_id)

            progress_bar.end()

        return compressor_executable_targets, prov_items

    @abstractproperty
    def compressor_aplx(self):
        """

        :return: The name of the compressor aplx file to use
        """

    def _generate_core_subsets(
            self, routing_tables, executable_finder, machine, progress_bar,
            system_executable_targets):
        """ generates the core subsets for the binaries

        :param ~.MulticastRoutingTables routing_tables: the routing tables
        :param ~.ExecutableFinder executable_finder: the executable path finder
        :param ~.Machine machine: the spinn machine instance
        :param ~.ProgressBar progress_bar: progress bar
        :param ExecutableTargets system_executable_targets:
            the executables targets to cores
        :return: (targets, sorter path, and compressor path)
        :rtype: tuple(ExecutableTargets, str, str)
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
            executable_finder.get_executable_path(self.compressor_aplx)

        # add the sets
        executable_targets.add_subsets(
            binary=bit_field_sorter_executable_path,
            subsets=bit_field_sorter_cores,
            executable_type=ExecutableType.SYSTEM)
        executable_targets.add_subsets(
            binary=bit_field_compressor_executable_path,
            subsets=bit_field_compressor_cores,
            executable_type=ExecutableType.SYSTEM)

        return (executable_targets, bit_field_sorter_executable_path,
                bit_field_compressor_executable_path)

    def _check_bit_field_router_compressor_for_success(
            self, executable_targets, transceiver, host_chips,
            sorter_binary_path, prov_data_items):
        """ Goes through the cores checking for cores that have failed to\
            generate the compressed routing tables with bitfield

        :param ExecutableTargets executable_targets:
            cores to load router compressor with bitfield on
        :param ~.Transceiver transceiver: SpiNNMan instance
        :param list(tuple(int,int)) host_chips:
            the chips which need to be ran on host.
        :param str sorter_binary_path: the path to the sorter binary
        :param list(ProvenanceDataItem) prov_data_items:
            the store of data items
        :rtype: bool
        """
        sorter_cores = executable_targets.get_cores_for_binary(
            sorter_binary_path)
        for core_subset in sorter_cores:
            x = core_subset.x
            y = core_subset.y

            for p in core_subset.processor_ids:

                # Read the result from USER1/USER2 registers
                user_1_base_address = \
                    transceiver.get_user_1_register_address_from_core(p)
                user_2_base_address = \
                    transceiver.get_user_2_register_address_from_core(p)
                result =  transceiver.read_word(x, y, user_1_base_address)
                bit_fields_merged =  transceiver.read_word(
                    x, y, user_2_base_address)

                if result != self.SUCCESS:
                    if (x, y) not in host_chips:
                        host_chips.append((x, y))
                    return False
                prov_data_items.append(generate_provenance_item(
                    x, y, bit_fields_merged))
        return True

    def _load_data(
            self, addresses, transceiver, routing_table_compressor_app_id,
            routing_tables, app_id, machine,
            compress_as_much_as_possible, progress_bar, cores,
            matrix_addresses_and_size, time_per_iteration,
            bit_field_compressor_executable_path,
            bit_field_sorter_executable_path, threshold_percentage):
        """ load all data onto the chip

        :param dict(tuple(int,int),tuple(int,int)) addresses:
            the addresses for bitfields in sdram
        :param ~.Transceiver transceiver: the spinnMan instance
        :param routing_table_compressor_app_id: the app id for the system app
        :param ~.MulticastRoutingTables routing_tables:
            the routing tables
        :param int app_id: the appid of the application
        :param ~.ProgressBar progress_bar: progress bar
        :param bool compress_as_much_as_possible:
            whether to compress as much as possible
        :param ExecutableTargets cores:
            the cores that compressor will run on
        :param dict matrix_addresses_and_size:
            maps chips to regeneration sdram and size for exploitation
        :param str bit_field_compressor_executable_path:
            the path to the compressor binary path
        :param str bit_field_sorter_executable_path:
            the path to the sorter binary
        :return:
            the list of tuples saying which chips this will need to use
            host compression, as the malloc failed.
        :rtype: list(tuple(int,int))
        """
        run_by_host = list()
        for table in routing_tables.routing_tables:
            if not machine.get_chip_at(table.x, table.y).virtual:
                try:
                    self._load_routing_table_data(
                        table, app_id, transceiver,
                        routing_table_compressor_app_id, progress_bar, cores,
                        matrix_addresses_and_size[(table.x, table.y)])

                    comms_sdram = transceiver.malloc_sdram(
                        table.x, table.y, SIZE_OF_COMMS_SDRAM,
                        routing_table_compressor_app_id)

                    self._load_address_data(
                        addresses, table.x, table.y, transceiver,
                        routing_table_compressor_app_id,
                        cores, matrix_addresses_and_size[(table.x, table.y)],
                        bit_field_compressor_executable_path,
                        bit_field_sorter_executable_path, comms_sdram,
                        threshold_percentage)

                    self._load_usable_sdram(
                        matrix_addresses_and_size[(table.x, table.y)], table.x,
                        table.y, transceiver, routing_table_compressor_app_id,
                        cores)

                    self._load_compressor_data(
                        table.x, table.y, time_per_iteration, transceiver,
                        bit_field_compressor_executable_path, cores,
                        compress_as_much_as_possible, comms_sdram)
                except CantFindSDRAMToUseException:
                    run_by_host.append((table.x, table.y))

        return run_by_host

    def _load_compressor_data(
            self, chip_x, chip_y, time_per_iteration, transceiver,
            bit_field_compressor_executable_path, cores,
            compress_as_much_as_possible,
            comms_sdram):
        """ Updates the user1 address for the compressor cores so they can \
            set the time per attempt.

        :param int chip_x: chip x coord
        :param int chip_y: chip y coord
        :param int time_per_iteration: time per attempt of compression
        :param ~.Transceiver transceiver: SpiNNMan instance
        :param str bit_field_compressor_executable_path:
            path for the compressor binary
        :param bool compress_as_much_as_possible:
            whether to compress as much as possible
        :param ExecutableTargets cores: the executable targets
        :param int comms_sdram: Address for comms block
        """
        compressor_cores = cores.get_cores_for_binary(
            bit_field_compressor_executable_path)
        for processor_id in compressor_cores.get_core_subset_for_chip(
                chip_x, chip_y).processor_ids:
            user1_address = \
                transceiver.get_user_1_register_address_from_core(processor_id)
            user2_address = \
                transceiver.get_user_2_register_address_from_core(processor_id)
            user3_address = \
                transceiver.get_user_3_register_address_from_core(processor_id)
            transceiver.write_memory(
                chip_x, chip_y, user1_address,
                self._ONE_WORDS.pack(
                    time_per_iteration * SECOND_TO_MICRO_SECOND),
                self._USER_BYTES)
            if compress_as_much_as_possible:
                compressor_setting = 1
            else:
                compressor_setting = 0
            transceiver.write_memory(
                chip_x, chip_y, user2_address,
                self._ONE_WORDS.pack(compressor_setting), self._USER_BYTES)
            transceiver.write_memory(
                chip_x, chip_y, user3_address,
                self._ONE_WORDS.pack(comms_sdram), self._USER_BYTES)

    def _load_usable_sdram(
            self, matrix_addresses_and_size, chip_x, chip_y, transceiver,
            routing_table_compressor_app_id, cores):
        """ loads the addresses of stealable sdram

        :param list(tuple(int,int)) matrix_addresses_and_size:
            SDRAM usable and sizes
        :param int chip_x: the chip x to consider here
        :param int chip_y: the chip y to consider here
        :param ~.Transceiver transceiver: the spinnman instance
        :param int routing_table_compressor_app_id: system app id.
        :param ExecutableTargets cores: the cores that compressor will run on
        """
        address_data = self._generate_chip_matrix_data(
            matrix_addresses_and_size)

        # get sdram address on chip
        try:
            sdram_address = transceiver.malloc_sdram(
                chip_x, chip_y, len(address_data),
                routing_table_compressor_app_id)
        except (SpinnmanInvalidParameterException,
                SpinnmanUnexpectedResponseCodeException):
            sdram_address = self._steal_from_matrix_addresses(
                matrix_addresses_and_size, len(address_data))
            address_data = self._generate_chip_matrix_data(
                matrix_addresses_and_size)

        # write sdram
        transceiver.write_memory(
            chip_x, chip_y, sdram_address, address_data, len(address_data))

        # get the only processor on the chip
        processor_id = list(cores.all_core_subsets.get_core_subset_for_chip(
            chip_x, chip_y).processor_ids)[0]

        # update user 2 with location
        user3_address = transceiver.get_user_3_register_address_from_core(
            processor_id)
        transceiver.write_memory(
            chip_x, chip_y, user3_address,
            self._ONE_WORDS.pack(sdram_address), self._USER_BYTES)

    def _generate_chip_matrix_data(self, list_of_sizes_and_address):
        """ generate the data for the chip matrix data

        :param list(tuple(int,int)) list_of_sizes_and_address:
            SDRAM addresses and sizes
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
            bit_field_sorter_executable_path, comms_sdram,
            threshold_percentage):
        """ loads the bitfield addresses space

        :param dict(tuple(int,int),tuple(int,int)) addresses:
            the addresses to load
        :param int chip_x: the chip x to consider here
        :param int chip_y: the chip y to consider here
        :param ~.Transceiver transceiver: the spinnman instance
        :param int routing_table_compressor_app_id: system app id.
        :param ExecutableTargets cores: the cores that compressor will run on
        :param str bit_field_compressor_executable_path:
            the path to the compressor binary path
        :param str bit_field_sorter_executable_path:
            the path to the sorter binary
        :param int comms_sdram: Address for comms block
        :param int threshold_percentage:
            the percentage of bitfields the user has defined as a minimum
            needed to pass to be successful.
        :rtype: None
        """
        # generate address_data
        address_data = self._generate_chip_data(
            addresses[(chip_x, chip_y)],
            cores.get_cores_for_binary(
                bit_field_compressor_executable_path).get_core_subset_for_chip(
                    chip_x, chip_y),
            comms_sdram, threshold_percentage)

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
        user2_address = transceiver.get_user_2_register_address_from_core(
            processor_id)
        transceiver.write_memory(
            chip_x, chip_y, user2_address,
            self._ONE_WORDS.pack(sdram_address), self._USER_BYTES)

    def _load_routing_table_data(
            self, table, app_id, transceiver,
            routing_table_compressor_app_id, progress_bar, cores,
            matrix_addresses_and_size):
        """ loads the routing table data

        :param AbsractMulticastRoutingTable table: the routing table to load
        :param int app_id: application app id
        :param ~.Transceiver transceiver: spinnman instance
        :param ~.ProgressBar progress_bar: progress bar
        :param int routing_table_compressor_app_id: system app id
        :param ExecutableTargets cores:
            the cores that the compressor going to run on
        :raises CantFindSDRAMToUse: when sdram is not malloc-ed or stolen
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
        user1_address = transceiver.get_user_1_register_address_from_core(
            processor_id)
        transceiver.write_memory(
            table.x, table.y, user1_address,
            self._ONE_WORDS.pack(base_address), self._USER_BYTES)

        # update progress bar
        progress_bar.update()

    def _build_routing_table_data(self, app_id, routing_table):
        """ builds routing data as needed for the compressor cores

        :param int app_id: appid of the application to load entries with
        :param ~.AbsractMulticastRoutingTable routing_table:
            the uncompressed routing table
        :return: data array
        :rtype: bytearray
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
                make_source_hack(entry=entry))
        return bytearray(data)

    @staticmethod
    def _steal_from_matrix_addresses(matrix_addresses_and_size, size_to_steal):
        """ steals memory from synaptic matrix as needed

        :param list(tuple(int,int)) matrix_addresses_and_size:
            matrix addresses and sizes
        :param int size_to_steal: size needed to steal from matrix's.
        :return: address to start steal from
        :rtype: int
        :raises CantFindSDRAMToUseException:
            when no space is big enough to steal from.
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
        """ adds data about the API-based vertex.

        :param AbstractSupportsBitFieldRoutingCompression vertex:
            vertex which utilises the API
        :param ~.Placement placement: placement of vertex
        :param ~.Transceiver transceiver:  spinnman instance
        :param dict(tuple(int,int),list(tuple(int,int))) region_addresses:
            store for data regions
        :param dict(tuple(int,int),list(tuple(int,int))) \
                sdram_block_addresses_and_sizes:
            store for surplus sdram.
        """
        # store the region sdram address's
        bit_field_sdram_address = vertex.bit_field_base_address(
            transceiver, placement)
        region_addresses[placement.x, placement.y].append(
            (bit_field_sdram_address, placement.p))

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
            self, machine_graph, placements, transceiver, progress_bar):
        """ generates the bitfield SDRAM addresses

        :param ~.MachineGraph machine_graph: machine graph
        :param ~.Placements placements: placements
        :param ~.Transceiver transceiver: spinnman instance
        :param ~.ProgressBar progress_bar: the progress bar
        :return: region_addresses and the executable targets to load the
            router table compressor with bitfield. and the SDRAM blocks
            available for use on each core that we plan to use
        :rtype: tuple(dict(tuple(int,int),tuple(int,int)),
            dict(tuple(int,int),list(tuple(int,int))))
        """
        # data holders
        region_addresses = defaultdict(list)
        sdram_block_addresses_and_sizes = defaultdict(list)

        for vertex in progress_bar.over(
                machine_graph.vertices, finish_at_end=False):
            placement = placements.get_placement_of_vertex(vertex)

            # locate the interface vertex (maybe app or machine)
            if isinstance(
                    vertex, AbstractSupportsBitFieldRoutingCompression):
                self._add_to_addresses(
                    vertex, placement, transceiver, region_addresses,
                    sdram_block_addresses_and_sizes)

        return region_addresses, sdram_block_addresses_and_sizes

    def _generate_chip_data(
            self, address_list, cores, comms_sdram, threshold_percentage):
        """ Generate byte array data for a list of SDRAM addresses and \
            finally the time to run per compression iteration.

        :param list(tuple(int,int)) address_list:
            the list of SDRAM addresses
        :param ~.CoreSubset cores: compressor cores on this chip.
        :param int comms_sdram: Address for comms block
        :param int threshold_percentage:
            the percentage of bitfields the user has defined as a minimum
            needed to pass to be successful.
        :return: the byte array
        :rtype: bytes
        """
        data = b""
        data += self._ONE_WORDS.pack(threshold_percentage)
        data += self._ONE_WORDS.pack(comms_sdram)
        data += self._ONE_WORDS.pack(len(address_list))
        for (bit_field, processor_id) in address_list:
            data += self._TWO_WORDS.pack(bit_field, processor_id)
        data += self._ONE_WORDS.pack(len(cores))
        compression_cores = list(cores.processor_ids)
        data += struct.pack("<{}I".format(len(cores)), *compression_cores)
        return data


class MachineBitFieldUnorderedRouterCompressor(
        MachineBitFieldRouterCompressor):

    @property
    @overrides(MachineBitFieldRouterCompressor.compressor_aplx)
    def compressor_aplx(self):
        return "bit_field_unordered_compressor.aplx"


class MachineBitFieldPairRouterCompressor(MachineBitFieldRouterCompressor):

    @property
    @overrides(MachineBitFieldRouterCompressor.compressor_aplx)
    def compressor_aplx(self):
        return "bit_field_pair_compressor.aplx"
