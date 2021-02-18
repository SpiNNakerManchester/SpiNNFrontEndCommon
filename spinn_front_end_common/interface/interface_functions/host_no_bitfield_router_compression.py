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
import struct
from spinn_utilities.log import FormatAdapter
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.executable_finder import ExecutableFinder
from spinn_machine import CoreSubsets, Router
from spinnman.model import ExecutableTargets
from spinnman.model.enums import CPUState
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException
from spinn_front_end_common.utilities.system_control_logic import (
    run_system_application)
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utilities.helpful_functions import (
    get_defaultable_source_id)
_FOUR_WORDS = struct.Struct("<IIII")
_THREE_WORDS = struct.Struct("<III")
# The SDRAM Tag used by the application - note this is fixed in the APLX
_SDRAM_TAG = 1

logger = FormatAdapter(logging.getLogger(__name__))


def mundy_on_chip_router_compression(
        routing_tables, transceiver, machine, app_id,
        system_provenance_folder, write_compressor_iobuf,
        compress_only_when_needed=True, compress_as_much_as_possible=False):
    """ Load routing tables and compress them using Andrew Mundy's algorithm.

    This uses an APLX built by Mundy which no longer compiles but still works
    with the current tool chain

    :param ~pacman.model.routing_tables.MulticastRoutingTables routing_tables:
        the memory routing tables to be compressed
    :param ~spinnman.transceiver.Transceiver transceiver:
        How to talk to the machine
    :param ~spinn_machine.Machine machine:
        the SpiNNaker machine representation
    :param int app_id: the application ID used by the main application
    :param str system_provenance_folder: the path to where to write the data
    :param bool compress_as_much_as_possible:
        If False, the compressor will only reduce the table until it fits in
        the router space, otherwise it will try to reduce until it until it
        can't reduce it any more
    :param bool compress_only_when_needed:
        If True, the compressor will only compress if the table doesn't fit in
        the current router space, otherwise it will just load the table
    :param bool write_compressor_iobuf: Should IOBUF be read and written out
    :raises SpinnFrontEndException: If compression fails
    """
    # pylint: disable=too-many-arguments, unused-argument
    msg = (
        "MundyOnChipRouterCompression is no longer supported. "
        "To use the currently recommended compression algorithm remove "
        "loading_algorithms from your cfg. "
        "While not recommended, OrderedCoveringOnChipRouterCompression "
        "provides the same algorithm but has been updated to use the "
        "current tools.")
    print(msg)
    logger.warning(msg)
    raise NotImplementedError(msg)


def pair_compression(
        routing_tables, transceiver, executable_finder,
        machine, app_id, provenance_file_path, write_compressor_iobuf,
        compress_as_much_as_possible=True):
    """ Load routing tables and compress then using the Pair Algorithm.

    See ``pacman/operations/router_compressors/pair_compressor.py`` which is
    the exact same algorithm implemented in Python.

    :param ~pacman.model.routing_tables.MulticastRoutingTables routing_tables:
        the memory routing tables to be compressed
    :param ~spinnman.transceiver.Transceiver transceiver:
        How to talk to the machine
    :param executable_finder: tracker of binaries.
    :type executable_finder:
        ~spinn_utilities.executable_finder.ExecutableFinder
    :param ~spinn_machine.Machine machine:
        the SpiNNaker machine representation
    :param int app_id: the application ID used by the main application
    :param str provenance_file_path: the path to where to write the data
    :param bool compress_as_much_as_possible:
        If False, the compressor will only reduce the table until it fits in
        the router space, otherwise it will try to reduce until it until it
        can't reduce it any more
    :param bool write_compressor_iobuf: Should IOBUF be read and written out
    :raises SpinnFrontEndException: If compression fails
     """
    # pylint: disable=too-many-arguments
    binary_path = executable_finder.get_executable_path(
        "simple_pair_compressor.aplx")
    compression = Compression(
        app_id, binary_path, compress_as_much_as_possible,
        machine, provenance_file_path, routing_tables, transceiver,
        "Running pair routing table compression on chip",
        write_compressor_iobuf, result_register=1)
    compression.compress()


def ordered_covering_compression(
        routing_tables, transceiver, executable_finder,
        machine, app_id, provenance_file_path, write_compressor_iobuf,
        compress_as_much_as_possible=True):
    """ Load routing tables and compress then using the unordered Algorithm.

    To the best of our knowledge this is the same algorithm as
    :py:func:`mundy_on_chip_router_compression`, except this one is still
    buildable and can be maintained.

    :param ~pacman.model.routing_tables.MulticastRoutingTables routing_tables:
        the memory routing tables to be compressed
    :param ~spinnman.transceiver.Transceiver transceiver:
        How to talk to the machine
    :param executable_finder: tracker of binaries.
    :type executable_finder:
        ~spinn_utilities.executable_finder.ExecutableFinder
    :param ~spinn_machine.Machine machine:
        the SpiNNaker machine representation
    :param int app_id: the application ID used by the main application
    :param str provenance_file_path: the path to where to write the data
    :param bool compress_as_much_as_possible:
        If False, the compressor will only reduce the table until it fits in
        the router space, otherwise it will try to reduce until it until it
        can't reduce it any more
    :param bool write_compressor_iobuf: Should IOBUF be read and written out
    :raises SpinnFrontEndException: If compression fails
    """
    # pylint: disable=too-many-arguments
    binary_path = executable_finder.get_executable_path(
        "simple_unordered_compressor.aplx")
    compression = Compression(
        app_id, binary_path, compress_as_much_as_possible,
        machine, provenance_file_path, routing_tables, transceiver,
        "Running unordered routing table compression on chip",
        write_compressor_iobuf, result_register=1)
    compression.compress()


def unordered_compression(
        routing_tables, transceiver, executable_finder,
        machine, app_id, provenance_file_path, write_compressor_iobuf,
        compress_as_much_as_possible=True):
    """ DEPRECATED use ordered_covering_compression """
    logger.warning(
        "UnorderedOnChipRouterCompression algorithm name is deprecated. "
        "Please use OrderedCoveringOnChipRouterCompression instead. "
        "loading_algorithms from your cfg to use defaults")
    ordered_covering_compression(
        routing_tables, transceiver, executable_finder,
        machine, app_id, provenance_file_path, write_compressor_iobuf,
        compress_as_much_as_possible)


class Compression(object):
    """ Compression algorithm implementation that uses a on-chip router\
        compressor in order to parallelise.
    """

    __slots__ = [
        "_app_id",
        "_binary_path",
        "_compress_as_much_as_possible",
        "_compress_only_when_needed",
        "_compressor_app_id",
        "_machine",
        "_progresses_text",
        "_provenance_file_path",
        "__result_register",
        "_transceiver",
        "_routing_tables",
        "_write_compressor_iobuf",
        "__failures"]

    def __init__(
            self, app_id, binary_path, compress_as_much_as_possible,
            machine, provenance_file_path, routing_tables, transceiver,
            progress_text, write_compressor_iobuf, result_register):
        """
        :param int app_id: the application ID used by the main application
        :param str binary_path: What binary to run
        :param bool compress_as_much_as_possible:
            Whether to do maximal compression
        :param ~spinn_machine.Machine machine: The machine model
        :param str provenance_file_path:
            Where to write provenance data (IOBUF contents)
        :param routing_tables: the memory routing tables to be compressed
        :type routing_tables:
            ~pacman.model.routing_tables.MulticastRoutingTables
        :param ~spinnman.transceiver.Transceiver transceiver:
            How to talk to the machine
        :param str progress_text: Text to use in progress bar
        :param bool write_compressor_iobuf:
            Should IOBUF be read and written out
        :param int result_register:
            number of the user register to check for the result code
        """
        self._app_id = app_id
        self._binary_path = binary_path
        self._compress_as_much_as_possible = compress_as_much_as_possible
        # Only used by mundy compressor we can not rebuild
        self._compress_only_when_needed = None
        self._machine = machine
        self._provenance_file_path = provenance_file_path
        self._transceiver = transceiver
        self._routing_tables = routing_tables
        self._progresses_text = progress_text
        self._compressor_app_id = None
        self._write_compressor_iobuf = write_compressor_iobuf
        self.__failures = []
        self.__result_register = result_register

    def compress(self):
        """ Apply the on-machine compression algorithm.

        :raises SpinnFrontEndException: If compression fails
        """
        # pylint: disable=too-many-arguments

        # build progress bar
        progress_bar = ProgressBar(
            len(self._routing_tables.routing_tables) * 2,
            self._progresses_text)

        if len(self._routing_tables.routing_tables) == 0:
            progress_bar.end()
            return

        self._compressor_app_id = self._transceiver.app_id_tracker.get_new_id()

        # figure size of SDRAM needed for each chip for storing the routing
        # table
        for routing_table in progress_bar.over(self._routing_tables, False):
            self._load_routing_table(routing_table)

        # load the router compressor executable
        executable_targets = self._load_executables()

        executable_finder = ExecutableFinder(binary_search_paths=[])
        run_system_application(
            executable_targets, self._compressor_app_id, self._transceiver,
            self._provenance_file_path, executable_finder,
            self._write_compressor_iobuf,
            self._check_for_success,
            [CPUState.FINISHED], False, "compressor_on_{}_{}_{}.txt",
            [self._binary_path], progress_bar)
        if self.__failures:
            raise SpinnFrontEndException(
                "The router compressor failed on {}".format(self.__failures))

    def _load_routing_table(self, table):
        """
        :param pacman.model.routing_tables.AbstractMulticastRoutingTable table:
            the pacman router table instance
        """
        data = self._build_data(table)

        # go to spinnman and ask for a memory region of that size per chip.
        base_address = self._transceiver.malloc_sdram(
            table.x, table.y, len(data), self._compressor_app_id, _SDRAM_TAG)

        # write SDRAM requirements per chip
        self._transceiver.write_memory(table.x, table.y, base_address, data)

    def _check_for_success(self, executable_targets, transceiver):
        """ Goes through the cores checking for cores that have failed to\
            compress the routing tables to the level where they fit into the\
            router

        :param ExecutableTargets executable_targets:
        :param ~spinnman.transceiver.Transceiver transceiver:
        """
        for core_subset in executable_targets.all_core_subsets:
            x = core_subset.x
            y = core_subset.y
            for p in core_subset.processor_ids:
                # Read the result from specified register
                if self.__result_register == 0:
                    result = transceiver.read_user_0(x, y, p)
                elif self.__result_register == 1:
                    result = transceiver.read_user_1(x, y, p)
                elif self.__result_register == 2:
                    result = transceiver.read_user_2(x, y, p)
                else:
                    raise Exception("Incorrect register")
                # The result is 0 if success, otherwise failure
                if result != 0:
                    self.__failures.append((x, y))
        return len(self.__failures) == 0

    def _load_executables(self):
        """ Plans the loading of the router compressor onto the chips.

        :return:
            the executable targets that represent all cores/chips which have
            active routing tables
        :rtype: ExecutableTargets
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
                                       ExecutableType.SYSTEM)

        return executable_targets

    def _build_data(self, table):
        """ Convert the router table into the data needed by the router\
            compressor C code.

        :param pacman.model.routing_tables.AbstractMulticastRoutingTable table:
            the pacman router table instance
        :return: The byte array of data
        :rtype: bytearray
        """

        # write header data of the app ID to load the data, if to store
        # results in SDRAM and the router table entries

        data = b''
        if self._compress_only_when_needed is None:
            data += _THREE_WORDS.pack(
                self._app_id,
                int(self._compress_as_much_as_possible),
                # Write the size of the table
                table.number_of_entries)
        else:
            # Mundy's compressor can not be changed so uses it own structure
            data += _FOUR_WORDS.pack(
                self._app_id, int(self._compress_only_when_needed),
                int(self._compress_as_much_as_possible),
                # Write the size of the table
                table.number_of_entries)

        for entry in table.multicast_routing_entries:
            data += _FOUR_WORDS.pack(
                entry.routing_entry_key, entry.mask,
                Router.convert_routing_table_entry_to_spinnaker_route(entry),
                get_defaultable_source_id(entry))
        return bytearray(data)
