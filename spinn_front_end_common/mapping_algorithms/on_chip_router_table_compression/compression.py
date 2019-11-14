# Copyright (c) 2017-2019 The University of Manchester
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

import logging
import os
import struct
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.executable_finder import ExecutableFinder
from spinn_machine import CoreSubsets, Router
from spinnman.model.enums import CPUState
from spinn_front_end_common.utilities.utility_objs import ExecutableTargets
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.interface.interface_functions import (
    ChipIOBufExtractor)

logger = logging.getLogger(__name__)
_FOUR_WORDS = struct.Struct("<IIII")
# The SDRAM Tag used by the application - note this is fixed in the APLX
_SDRAM_TAG = 1


def mundy_on_chip_router_compression(
        routing_tables, transceiver, machine, app_id,
        system_provenance_folder, compress_only_when_needed=True,
        compress_as_much_as_possible=False):
    """
    Load routing tables and compress then using Mundy's algorithm

    :param routing_tables: the memory routing tables to be compressed
    :param transceiver: the spinnman interface
    :param machine: the SpiNNaker machine representation
    :param app_id: the application ID used by the main application
    :param system_provenance_folder: the path to where to write the data
    :param compress_as_much_as_possible:\
        If False, the compressor will only reduce the table until it fits\
        in the router space, otherwise it will try to reduce until it\
        until it can't reduce it any more
    :type compress_as_much_as_possible: bool
    :param compress_only_when_needed:\
        If True, the compressor will only compress if the table doesn't\
        fit in the current router space, otherwise it will just load\
        the table
    :type compress_only_when_needed: bool
    :return:
    """
    # pylint: disable=too-many-arguments
    binary_path = os.path.join(os.path.dirname(__file__), "rt_minimise.aplx")
    compression = _Compression(
        app_id, binary_path, compress_as_much_as_possible,
        compress_only_when_needed, machine, system_provenance_folder,
        routing_tables, transceiver)
    compression._compress()


def pair_compression(
        routing_tables, transceiver, executable_finder,
        machine, app_id, provenance_file_path,
        compress_only_when_needed=False,
        compress_as_much_as_possible=True):
    """
    Load routing tables and compress then using Pair Algorithm

    See pacman/operations/router_compressors/pair_compressor.py which is the
        exact same algorithm implemented in python

    :param routing_tables: the memory routing tables to be compressed
    :param transceiver: the spinnman interface
    :param executable_finder:
    :param machine: the SpiNNaker machine representation
    :param app_id: the application ID used by the main application
    :param provenance_file_path: the path to where to write the data
    :param compress_as_much_as_possible:\
        If False, the compressor will only reduce the table until it fits\
        in the router space, otherwise it will try to reduce until it\
        until it can't reduce it any more
    :type compress_as_much_as_possible: bool
    :param compress_only_when_needed:\
        If True, the compressor will only compress if the table doesn't\
        fit in the current router space, otherwise it will just load\
        the table
    :type compress_only_when_needed: bool
     """
    # pylint: disable=too-many-arguments
    binary_path = executable_finder.get_executable_path(
        "simple_minimise.aplx")
    compression = _Compression(
        app_id, binary_path, compress_as_much_as_possible,
        compress_only_when_needed, machine, provenance_file_path,
        routing_tables, transceiver)
    compression._compress()


class _Compression(object):
    """ Compressor that uses a on chip router compressor
    """

    __slots__ = ["_app_id",
                 "_binary_path",
                 "_compress_as_much_as_possible",
                 "_compress_only_when_needed",
                 "_compressor_app_id",
                 "_machine",
                 "_provenance_file_path",
                 "_transceiver",
                 "_routing_tables",
                 ]

    def __init__(
            self, app_id, binary_path, compress_as_much_as_possible,
            compress_only_when_needed, machine, provenance_file_path,
            routing_tables, transceiver):
        self._app_id = app_id
        self._binary_path = binary_path
        self._compress_as_much_as_possible = compress_as_much_as_possible
        self._compress_only_when_needed = compress_only_when_needed
        self._machine = machine
        self._provenance_file_path = provenance_file_path
        self._transceiver = transceiver
        self._routing_tables = routing_tables

    def _compress(self):
        """
        :return: flag stating routing compression and loading has been done
        """
        # pylint: disable=too-many-arguments

        # build progress bar
        progress = ProgressBar(
            len(self._routing_tables.routing_tables) + 2,
            "Running routing table compression on chip")

        self._compressor_app_id = self._transceiver.app_id_tracker.get_new_id()

        # figure size of SDRAM needed for each chip for storing the routing
        # table
        for routing_table in progress.over(self._routing_tables, False):
            self._load_routing_table(routing_table)

        # load the router compressor executable
        executable_targets = self._load_executables()

        # update progress bar
        progress.update()

        # Wait for the executable to finish
        succeeded = False
        try:
            self._transceiver.wait_for_cores_to_be_in_state(
                executable_targets.all_core_subsets, self._compressor_app_id,
                [CPUState.FINISHED])
            succeeded = True
        finally:
            # get the debug data
            if not succeeded:
                self._handle_failure(
                    executable_targets)

        # Check if any cores have not completed successfully
        self._check_for_success(executable_targets)

        # update progress bar
        progress.update()

        # stop anything that's associated with the compressor binary
        self._transceiver.stop_application(self._compressor_app_id)
        self._transceiver.app_id_tracker.free_id(self._compressor_app_id)

        # update the progress bar
        progress.end()

    def _load_routing_table(self, table):
        data = self._build_data(table)

        # go to spinnman and ask for a memory region of that size per chip.
        base_address = self._transceiver.malloc_sdram(
            table.x, table.y, len(data), self._compressor_app_id, _SDRAM_TAG)

        # write SDRAM requirements per chip
        self._transceiver.write_memory(table.x, table.y, base_address, data)

    def _check_for_success(self, executable_targets):
        """ Goes through the cores checking for cores that have failed to\
            compress the routing tables to the level where they fit into the\
            router
        """

        for core_subset in executable_targets.all_core_subsets:
            x = core_subset.x
            y = core_subset.y
            for p in core_subset.processor_ids:
                # Read the result from USER0 register
                result = self._transceiver.read_user_0(x, y, p)

                # The result is 0 if success, otherwise failure
                if result != 0:
                    self._handle_failure(executable_targets)

                    raise SpinnFrontEndException(
                        "The router compressor on {}, {} failed to complete"
                        .format(x, y))

    def _handle_failure(self, executable_targets):
        logger.info("Router compressor has failed")
        iobuf_extractor = ChipIOBufExtractor()
        executable_finder = ExecutableFinder(binary_search_paths=[])
        io_errors, io_warnings = iobuf_extractor(
            self._transceiver, executable_targets, executable_finder,
            self._provenance_file_path)
        for warning in io_warnings:
            logger.warning(warning)
        for error in io_errors:
            logger.error(error)
        self._transceiver.stop_application(self._compressor_app_id)
        self._transceiver.app_id_tracker.free_id(self._compressor_app_id)

    def _load_executables(self):
        """ Loads the router compressor onto the chips.

        :return:\
            the executable targets that represent all cores/chips which have\
            active routing tables
        """

        # build core subsets
        core_subsets = CoreSubsets()
        for routing_table in self._routing_tables:

            # get the first none monitor core
            chip = self._machine.get_chip_at(routing_table.x, routing_table.y)
            processor = chip.get_first_none_monitor_processor()

            # add to the core subsets
            core_subsets.add_processor(
                routing_table.x, routing_table.y, processor.processor_id)

        # build executable targets
        executable_targets = ExecutableTargets()
        executable_targets.add_subsets(self._binary_path, core_subsets,
                                       ExecutableType.RUNNING)

        self._transceiver.execute_application(
            executable_targets, self._compressor_app_id)
        return executable_targets

    def _build_data(self, routing_table):
        """ Convert the router table into the data needed by the router\
            compressor c code.

       :param routing_table: the pacman router table instance
       :return: The byte array of data
        """

        # write header data of the app ID to load the data, if to store
        # results in SDRAM and the router table entries

        data = b''
        data += _FOUR_WORDS.pack(
            self._app_id, int(self._compress_only_when_needed),
            int(self._compress_as_much_as_possible),
            # Write the size of the table
            routing_table.number_of_entries)

        for entry in routing_table.multicast_routing_entries:
            data += _FOUR_WORDS.pack(
                entry.routing_entry_key, entry.mask,
                Router.convert_routing_table_entry_to_spinnaker_route(entry),
                self._make_source_hack(entry))
        return bytearray(data)

    def _make_source_hack(self, entry):
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
