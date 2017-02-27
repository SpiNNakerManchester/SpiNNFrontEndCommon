from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.interface.interface_functions. \
    front_end_common_provenance_xml_writer import \
    FrontEndCommonProvenanceXMLWriter
from spinn_front_end_common.mapping_algorithms \
    import on_chip_router_table_compression
from spinn_front_end_common.interface.interface_functions.\
    front_end_common_chip_iobuf_extractor import \
    FrontEndCommonChipIOBufExtractor
from spinn_front_end_common.interface.interface_functions.\
    front_end_common_load_executable_images import \
    FrontEndCommonLoadExecutableImages
from spinn_front_end_common.utilities.utility_objs. \
    provenance_data_item import ProvenanceDataItem
from spinnman.model.enums.executable_start_type import ExecutableStartType

from spinnman.model.executable_targets import \
    ExecutableTargets
from spinnman import transceiver as tx
from spinnman import exceptions as spinnman_exceptions

from spinn_machine.core_subsets import CoreSubsets
from spinn_machine.router import Router
from spinn_machine.utilities.progress_bar import ProgressBar

import logging
import os
import struct
import time

logger = logging.getLogger(__name__)


class MundyOnChipRouterCompression(object):
    """ Compressor that uses a on chip router compressor
    """

    SIZE_OF_A_SDRAM_ENTRY = 4 * 4
    SURPLUS_DATA_ENTRIES = 3 * 4
    TIME_EXPECTED_TO_RUN = 1000
    OVER_RUN_THRESHOLD_BEFORE_ERROR = 1000

    def __call__(
            self, routing_tables, transceiver, machine, app_app_id,
            compressor_app_id, provenance_file_path, store_on_sdram=False,
            sdram_tag=1, record_iobuf=True, compress_only_when_needed=False,
            use_default_target_length=False, provenance_data_objects=None):
        """

        :param routing_tables: the memory routing tables to be compressed
        :param app_app_id: the app-id used by the main application
        :param store_on_sdram:\
            flag to say store it on sdram or in the routing table
        :param provenance_file_path: the path to where to write the data
        :param machine: the spinnaker machine representation
        :param transceiver: the spinnman interface
        :return: flag stating routing compression and loading hath been done
        """

        if provenance_data_objects is not None:
            prov_items = provenance_data_objects
        else:
            prov_items = list()

        # build progress bar
        progress_bar = ProgressBar(
            len(routing_tables.routing_tables) + 2,
            "Running routing table compression on chip")

        # figure size of sdram needed for each chip for storing the routing
        # table
        for routing_table in routing_tables:

            data = self._build_data(
                routing_table, app_app_id, store_on_sdram,
                compress_only_when_needed, use_default_target_length)
            chip = machine.get_chip_at(routing_table.x, routing_table.y)

            if len(data) > chip.sdram:
                raise exceptions.ConfigurationException(
                    "There is not enough memory on the chip to write the "
                    "routing tables into.")

            # go to spinnman and ask for a memory region of that size per chip.
            base_address = transceiver.malloc_sdram(
                routing_table.x, routing_table.y, len(data),
                compressor_app_id, sdram_tag)

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

        # get logger for spinnman and turn off
        tx_logger = tx.logger
        logger_level = tx_logger.level
        tx_logger.setLevel(logging.ERROR)

        # verify when the executable has finished
        start_time = time.time()
        try:
            transceiver.poll_for_execution_to_complete(
                executable_targets.all_core_subsets, compressor_app_id)
            stop_time = time.time()
            self._check_for_correct_complete_code(
                executable_targets, transceiver, stop_time - start_time,
                provenance_file_path, prov_items, compressor_app_id)
            tx_logger.setLevel(logger_level)
        except spinnman_exceptions.ExecutableFailedToStopException:
            # get the debug data
            stop_time = time.time()
            self._handle_failure(
                executable_targets, transceiver, provenance_file_path,
                stop_time - start_time, prov_items, compressor_app_id)

        # update progress bar
        progress_bar.update()

        # get debug info if requested
        if record_iobuf:
            self._acquire_iobuf(executable_targets, transceiver,
                                provenance_file_path)

        # stop anything that's associated with the compressor binary
        transceiver.stop_application(compressor_app_id)

        # update the progress bar
        progress_bar.end()

        # create provenance data item
        prov_items = self._create_provenance_data_item(
            stop_time - start_time, prov_items)

        # return loaded routing tables flag
        return True, prov_items

    def _check_for_correct_complete_code(
            self, executable_targets, transceiver, duration,
            provenance_file_path, prov_items, compressor_app_id):
        """ goes through the cores checking for cores that have failed to
        compress the routing tables to the level where they fit into the router

        :param
        compressor on them
        :param transceiver: the main spinnman interface
        :return: None
        :raises
        """

        for core_subset in executable_targets.all_core_subsets:
            x = core_subset.x
            y = core_subset.y
            for p in core_subset.processor_ids:
                user_0_address = \
                    transceiver.get_user_0_register_address_from_core(x, y, p)

                data = struct.unpack(
                    "<I", str(
                        transceiver.read_memory(x, y, user_0_address, 4)))[0]
                if data != 0:
                    self._handle_failure(
                        executable_targets, transceiver, provenance_file_path,
                        duration, prov_items, compressor_app_id)

    def _handle_failure(
            self, executable_targets, transceiver, provenance_file_path,
            duration, prov_items, compressor_app_id):
        """

        :param executable_targets:
        :param transceiver:
        :param provenance_file_path:
        :param duration:
        :param prov_items:
        :return:
        """
        self._get_debug_data(
            executable_targets, transceiver, provenance_file_path)
        self._write_provenance_data(duration, prov_items, provenance_file_path)
        transceiver.stop_application(compressor_app_id)
        raise exceptions.SpinnFrontEndException(
            "The router compressor failed to complete")

    def _get_debug_data(
            self, executable_targets, transceiver, provenance_file_path):
        """ get data from the machine for debug purposes when the compressor\
            fails

        :param executable_targets:\
            executable targets that represent all cores/chips which have\
            active routing tables
        :param transceiver: the spinnman interface
        :param provenance_file_path: the path to where to write the data
        :return:
        """
        logger.info("acquiring debug data from router compressor crash")
        io_errors, io_warnings = self._acquire_iobuf(
            executable_targets, transceiver, provenance_file_path)
        for warning in io_warnings:
            logger.warn(warning)
        for error in io_errors:
            logger.error(error)

    def _write_provenance_data(
            self, duration, prov_items, provenance_file_path):
        prov_items = self._create_provenance_data_item(duration, prov_items)
        prov_writer = FrontEndCommonProvenanceXMLWriter()
        prov_writer(prov_items, provenance_file_path)

    @staticmethod
    def _create_provenance_data_item(duration, prov_items):
        names = ["on_chip_routing_table_compressor_run_time"]
        prov_items.append(ProvenanceDataItem(names, str(duration)))
        return prov_items

    def _acquire_iobuf(self, executable_targets, transceiver,
                       provenance_file_path):
        """ Get the iobuf from the router compressor cores

        :param executable_targets: the mapping between binary and cores
        :param transceiver: the spinnman interface
        :param provenance_file_path: the path to where to write the data
        :return:
        """
        iobuf_extractor = FrontEndCommonChipIOBufExtractor()
        io_buffers, io_errors, io_warnings = iobuf_extractor(
            transceiver, True, executable_targets.get_start_core_subsets(
                ExecutableStartType.RUNNING))
        self._write_iobuf(io_buffers, provenance_file_path)
        return io_errors, io_warnings

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
        core_subsets = self._build_core_subsets(routing_tables, machine)

        # build binary path
        binary_path = os.path.join(
            os.path.dirname(on_chip_router_table_compression.__file__),
            "rt_minimise.aplx")

        # build executable targets
        executable_targets = ExecutableTargets()
        executable_targets.add_subsets(
            binary_path, core_subsets, ExecutableStartType.RUNNING)

        executable_loader = FrontEndCommonLoadExecutableImages()
        success = executable_loader(
            executable_targets, compressor_app_id, transceiver, True, False)
        if not success:
            raise exceptions.ConfigurationException(
                "The app loader failed to load the executable for router "
                "compression.")
        return executable_targets

    def _build_data(self, routing_table, app_id, store_on_sdram,
                    compress_only_when_needed, use_default_target_length):
        """ convert the router table into the data needed by the router\
            compressor c code.

        :param routing_table: the pacman router table instance
        :param app_id: the app-id to load the entries in by
        :param store_on_sdram: flag that says store the results in sdram
        :param compress_only_when_needed:\
            flag that tells the c code to compress at all times or only when\
            needed
        :param use_default_target_length:\
            flag that lets the compressor compress as far as possible, or only\
            till it meets the router table available size.
        :return: The byte array needed for spinnman
        """

        # write header data of the app id to load the data, if to store
        # results in sdram and the router table entries

        data = b''
        data += struct.pack("<I", app_id)
        data += struct.pack("<I", int(compress_only_when_needed))
        data += struct.pack("<I", int(use_default_target_length))
        data += struct.pack("<I", store_on_sdram)
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

    @staticmethod
    def _build_core_subsets(routing_tables, machine):
        """ builds the mapping for a core on each chip to have a router\
            compressor.

        :param routing_tables: the routing tables to be loaded for compression
        :param machine: the spinnaker machine representation
        :return: a core subsets representing all the routing tables
        """
        core_sets = CoreSubsets()
        for routing_table in routing_tables:
            # get the first none monitor core
            chip = machine.get_chip_at(routing_table.x, routing_table.y)
            processor = chip.get_first_none_monitor_processor()

            # add to the core subsets
            core_sets.add_processor(routing_table.x, routing_table.y,
                                    processor.processor_id)
        return core_sets
