from spinn_utilities.progress_bar import ProgressBar

from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException
from spinn_front_end_common.mapping_algorithms \
    import on_chip_router_table_compression
from spinn_front_end_common.interface.interface_functions \
    import ChipIOBufExtractor

from spinnman.model.enums import CPUState
from spinnman.model import ExecutableTargets

from spinn_machine import CoreSubsets, Router

import logging
import os
import struct

logger = logging.getLogger(__name__)
_ONE_WORD = struct.Struct("<I")
_FOUR_WORDS = struct.Struct("<IIII")
# The SDRAM Tag used by the application - note this is fixed in the APLX
_SDRAM_TAG = 1
_BINARY_PATH = os.path.join(
    os.path.dirname(on_chip_router_table_compression.__file__),
    "rt_minimise.aplx")


class MundyOnChipRouterCompression(object):
    """ Compressor that uses a on chip router compressor
    """

    SIZE_OF_A_SDRAM_ENTRY = 4 * 4
    SURPLUS_DATA_ENTRIES = 3 * 4
    TIME_EXPECTED_TO_RUN = 1000
    OVER_RUN_THRESHOLD_BEFORE_ERROR = 1000

    def __call__(
            self, routing_tables, transceiver, machine, app_id,
            provenance_file_path, compress_only_when_needed=True,
            compress_as_much_as_possible=False):
        """
        :param routing_tables: the memory routing tables to be compressed
        :param transceiver: the spinnman interface
        :param machine: the SpiNNaker machine representation
        :param app_id: the application ID used by the main application
        :param provenance_file_path: the path to where to write the data
        :return: flag stating routing compression and loading has been done
        """
        # pylint: disable=too-many-arguments

        # build progress bar
        progress = ProgressBar(
            len(routing_tables.routing_tables) + 2,
            "Running routing table compression on chip")
        compressor_app_id = transceiver.app_id_tracker.get_new_id()

        # figure size of SDRAM needed for each chip for storing the routing
        # table
        for routing_table in progress.over(routing_tables, False):
            self._load_routing_table(
                routing_table, transceiver, app_id, compressor_app_id,
                compress_only_when_needed, compress_as_much_as_possible)

        # load the router compressor executable
        executable_targets = self._load_executables(
            routing_tables, compressor_app_id, transceiver, machine)

        # update progress bar
        progress.update()

        # Wait for the executable to finish
        succeeded = False
        try:
            transceiver.wait_for_cores_to_be_in_state(
                executable_targets.all_core_subsets, compressor_app_id,
                [CPUState.FINISHED])
            succeeded = True
        finally:
            # get the debug data
            if not succeeded:
                self._handle_failure(
                    executable_targets, transceiver, provenance_file_path,
                    compressor_app_id)

        # Check if any cores have not completed successfully
        self._check_for_success(
            executable_targets, transceiver,
            provenance_file_path, compressor_app_id)

        # update progress bar
        progress.update()

        # stop anything that's associated with the compressor binary
        transceiver.stop_application(compressor_app_id)
        transceiver.app_id_tracker.free_id(compressor_app_id)

        # update the progress bar
        progress.end()

    def _load_routing_table(
            self, table, txrx, app_id, compressor_app_id,
            compress_only_when_needed, compress_as_much_as_possible):
        # pylint: disable=too-many-arguments
        data = self._build_data(
            table, app_id, compress_only_when_needed,
            compress_as_much_as_possible)

        # go to spinnman and ask for a memory region of that size per chip.
        base_address = txrx.malloc_sdram(
            table.x, table.y, len(data), compressor_app_id, _SDRAM_TAG)

        # write SDRAM requirements per chip
        txrx.write_memory(table.x, table.y, base_address, data)

    @staticmethod
    def __read_user_0(txrx, x, y, p):
        addr = txrx.get_user_0_register_address_from_core(p)
        return struct.unpack("<I", txrx.read_memory(x, y, addr, 4))[0]

    def _check_for_success(
            self, executable_targets, txrx, provenance_file_path,
            compressor_app_id):
        """ Goes through the cores checking for cores that have failed to\
            compress the routing tables to the level where they fit into the\
            router
        """

        for core_subset in executable_targets.all_core_subsets:
            x = core_subset.x
            y = core_subset.y
            for p in core_subset.processor_ids:
                # Read the result from USER0 register
                result = self.__read_user_0(txrx, x, y, p)

                # The result is 0 if success, otherwise failure
                if result != 0:
                    self._handle_failure(
                        executable_targets, txrx, provenance_file_path,
                        compressor_app_id)

                    raise SpinnFrontEndException(
                        "The router compressor on {}, {} failed to complete"
                        .format(x, y))

    @staticmethod
    def _handle_failure(
            executable_targets, txrx, provenance_file_path, compressor_app_id):
        """
        :param executable_targets:
        :param txrx:
        :param provenance_file_path:
        :rtype: None
        """
        logger.info("Router compressor has failed")
        iobuf_extractor = ChipIOBufExtractor()
        io_errors, io_warnings = iobuf_extractor(
            txrx, executable_targets.all_core_subsets,
            provenance_file_path)
        for warning in io_warnings:
            logger.warning(warning)
        for error in io_errors:
            logger.error(error)
        txrx.stop_application(compressor_app_id)
        txrx.app_id_tracker.free_id(compressor_app_id)

    @staticmethod
    def _load_executables(routing_tables, compressor_app_id, txrx, machine):
        """ Loads the router compressor onto the chips.

        :param routing_tables: the router tables needed to be compressed
        :param compressor_app_id: the app ID of the compressor compressor
        :param txrx: the spinnman interface
        :param machine: the SpiNNaker machine representation
        :return:\
            the executable targets that represent all cores/chips which have\
            active routing tables
        """

        # build core subsets
        core_subsets = CoreSubsets()
        for routing_table in routing_tables:

            # get the first none monitor core
            chip = machine.get_chip_at(routing_table.x, routing_table.y)
            processor = chip.get_first_none_monitor_processor()

            # add to the core subsets
            core_subsets.add_processor(
                routing_table.x, routing_table.y, processor.processor_id)

        # build executable targets
        executable_targets = ExecutableTargets()
        executable_targets.add_subsets(_BINARY_PATH, core_subsets)

        txrx.execute_application(executable_targets, compressor_app_id)
        return executable_targets

    def _build_data(
            self, routing_table, app_id, compress_only_when_needed,
            compress_as_much_as_possible):
        """ Convert the router table into the data needed by the router\
            compressor c code.

        :param routing_table: the pacman router table instance
        :param app_id: the application ID to load the entries in by
        :param compress_only_when_needed:\
            If True, the compressor will only compress if the table doesn't\
            fit in the current router space, otherwise it will just load\
            the table
        :type compress_only_when_needed: bool
        :param compress_as_much_as_possible:\
            If False, the compressor will only reduce the table until it fits\
            in the router space, otherwise it will try to reduce until it\
            until it can't reduce it any more
        :type compress_as_much_as_possible: bool
        :return: The byte array of data
        """

        # write header data of the app ID to load the data, if to store
        # results in SDRAM and the router table entries

        data = b''
        data += _FOUR_WORDS.pack(
            app_id, int(compress_only_when_needed),
            int(compress_as_much_as_possible),
            # Write the size of the table
            routing_table.number_of_entries)

        for entry in routing_table.multicast_routing_entries:
            data += _FOUR_WORDS.pack(
                entry.routing_entry_key, entry.mask,
                Router.convert_routing_table_entry_to_spinnaker_route(entry),
                self._make_source_hack(entry))
        return bytearray(data)

    @staticmethod
    def _make_source_hack(entry):
        """ Hack to support the source requirement for the router compressor\
            on chip

        :param entry: the multicast router table entry.
        :return: return the source value
        """
        if entry.defaultable:
            return (list(entry.link_ids)[0] + 3) % 6
        elif entry.link_ids:
            return list(entry.link_ids)[0]
        return 0
