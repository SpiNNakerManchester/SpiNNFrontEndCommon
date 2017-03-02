from spinn_front_end_common.utilities import exceptions
from spinnman.model.enums.cpu_state import CPUState
import sys
from spinn_front_end_common.mapping_algorithms \
    import on_chip_router_table_compression
from spinn_front_end_common.interface.interface_functions.\
    front_end_common_chip_iobuf_extractor import \
    FrontEndCommonChipIOBufExtractor

from spinnman.model.executable_targets import \
    ExecutableTargets

from spinn_machine.core_subsets import CoreSubsets
from spinn_machine.router import Router
from spinn_machine.utilities.progress_bar import ProgressBar

import logging
import os
import struct

logger = logging.getLogger(__name__)

# The SDRAM Tag used by the application - note this is fixed in the APLX
_SDRAM_TAG = 1


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
        :param machine: the spinnaker machine representation
        :param app_id: the app-id used by the main application
        :param provenance_file_path: the path to where to write the data
        :return: flag stating routing compression and loading has been done
        """

        # build progress bar
        progress_bar = ProgressBar(
            len(routing_tables.routing_tables) + 2,
            "Running routing table compression on chip")
        compressor_app_id = transceiver.app_id_tracker.get_new_id()

        # figure size of sdram needed for each chip for storing the routing
        # table
        for routing_table in routing_tables:

            data = self._build_data(
                routing_table, app_id, compress_only_when_needed,
                compress_as_much_as_possible)

            # go to spinnman and ask for a memory region of that size per chip.
            base_address = transceiver.malloc_sdram(
                routing_table.x, routing_table.y, len(data),
                compressor_app_id, _SDRAM_TAG)

            # write sdram requirements per chip
            transceiver.write_memory(
                routing_table.x, routing_table.y, base_address, data)

            # update progress bar
            progress_bar.update()

        # load the router compressor executable
        executable_targets = self._load_executables(
            routing_tables, compressor_app_id, transceiver, machine)

        # update progress bar
        progress_bar.update()

        # Wait for the executable to finish
        try:
            transceiver.wait_for_cores_to_be_in_state(
                executable_targets.all_core_subsets, compressor_app_id,
                [CPUState.FINISHED])
        except:

            # get the debug data
            self._handle_failure(
                executable_targets, transceiver, provenance_file_path,
                compressor_app_id)

            exc_type, exc_value, exc_traceback = sys.exc_info()
            raise exc_type, exc_value, exc_traceback

        # Check if any cores have not completed successfully
        self._check_for_success(
            executable_targets, transceiver,
            provenance_file_path, compressor_app_id)

        # update progress bar
        progress_bar.update()

        # stop anything that's associated with the compressor binary
        transceiver.stop_application(compressor_app_id)
        transceiver.app_id_tracker.free_id(compressor_app_id)

        # update the progress bar
        progress_bar.end()

        # return loaded routing tables flag
        return True

    def _check_for_success(
            self, executable_targets, transceiver, provenance_file_path,
            compressor_app_id):
        """ goes through the cores checking for cores that have failed to\
            compress the routing tables to the level where they fit into the\
            router
        """

        for core_subset in executable_targets.all_core_subsets:
            x = core_subset.x
            y = core_subset.y
            for p in core_subset.processor_ids:

                # Read the result from USER0 register
                user_0_address = \
                    transceiver.get_user_0_register_address_from_core(x, y, p)

                result = struct.unpack(
                    "<I", str(transceiver.read_memory(x, y, user_0_address, 4))
                )[0]

                # The result is 0 if success, otherwise failure
                if result != 0:
                    self._handle_failure(
                        executable_targets, transceiver, provenance_file_path,
                        compressor_app_id)

                    raise exceptions.SpinnFrontEndException(
                        "The router compressor on {}, {} failed to complete"
                        .format(x, y))

    def _handle_failure(
            self, executable_targets, transceiver, provenance_file_path,
            compressor_app_id):
        """

        :param executable_targets:
        :param transceiver:
        :param provenance_file_path:
        :param prov_items:
        :return:
        """
        logger.info("Router compressor has failed")
        iobuf_extractor = FrontEndCommonChipIOBufExtractor()
        io_buffers, io_errors, io_warnings = iobuf_extractor(
            transceiver, True, executable_targets.all_core_subsets)
        self._write_iobuf(io_buffers, provenance_file_path)
        for warning in io_warnings:
            logger.warn(warning)
        for error in io_errors:
            logger.error(error)
        transceiver.stop_application(compressor_app_id)
        transceiver.app_id_tracker.free_id(compressor_app_id)

    @staticmethod
    def _write_iobuf(io_buffers, provenance_file_path):
        """ writes the iobuf to files

        :param io_buffers: the iobuf for the cores
        :param provenance_file_path:\
            the file path where the iobuf are to be stored
        :return: None
        """
        for iobuf in io_buffers:
            file_name = os.path.join(
                provenance_file_path,
                "{}_{}_{}_compressor.txt".format(iobuf.x, iobuf.y, iobuf.p))
            count = 2
            while os.path.exists(file_name):
                file_name = os.path.join(
                    provenance_file_path,
                    "{}_{}_{}_compressor-{}.txt".format(
                        iobuf.x, iobuf.y, iobuf.p, count))
                count += 1
            writer = open(file_name, "w")
            writer.write(iobuf.iobuf)
            writer.close()

    def _load_executables(
            self, routing_tables, compressor_app_id, transceiver, machine):
        """ loads the router compressor onto the chips.

        :param routing_tables: the router tables needed to be compressed
        :param compressor_app_id: the app id of the compressor compressor
        :param transceiver: the spinnman interface
        :param machine: the spinnaker machine representation
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

        # build binary path
        binary_path = os.path.join(
            os.path.dirname(on_chip_router_table_compression.__file__),
            "rt_minimise.aplx")

        # build executable targets
        executable_targets = ExecutableTargets()
        executable_targets.add_subsets(binary_path, core_subsets)

        transceiver.execute_application(executable_targets, compressor_app_id)
        return executable_targets

    def _build_data(
            self, routing_table, app_id, compress_only_when_needed,
            compress_as_much_as_possible):
        """ convert the router table into the data needed by the router\
            compressor c code.

        :param routing_table: the pacman router table instance
        :param app_id: the app-id to load the entries in by
        :param compress_only_when_needed:\
            If True, the compressor will only compress if the table doesn't\
            fit in the current router space, otherwise it will just load\
            the table
        :param compress_as_much_as_possible:\
            If False, the compressor will only reduce the table until it fits\
            in the router space, otherwise it will try to reduce until it\
            until it can't reduce it any more
        :return: The byte array of data
        """

        # write header data of the app id to load the data, if to store
        # results in sdram and the router table entries

        data = b''
        data += struct.pack("<I", app_id)
        data += struct.pack("<I", int(compress_only_when_needed))
        data += struct.pack("<I", int(compress_as_much_as_possible))

        # Write the size of the table
        data += struct.pack("<I", routing_table.number_of_entries)

        for entry in routing_table.multicast_routing_entries:
            data += struct.pack("<I", entry.routing_entry_key)
            data += struct.pack("<I", entry.mask)
            data += struct.pack(
                "<I",
                Router.convert_routing_table_entry_to_spinnaker_route(entry))
            data += struct.pack("<I", self._make_source_hack(entry))
        return bytearray(data)

    @staticmethod
    def _make_source_hack(entry):
        """ Hack to support the source requirement for the router compressor\
            on chip
        :param entry: the multicast router table entry.
        :return: return the source value
        """
        if entry.defaultable:
            return list(entry.link_ids)[0] + 3 % 6
        elif len(entry.link_ids) > 0:
            return list(entry.link_ids)[0]
        else:
            return 0
