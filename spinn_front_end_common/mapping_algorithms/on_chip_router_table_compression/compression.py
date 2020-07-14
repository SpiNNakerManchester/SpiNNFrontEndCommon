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

import functools
import logging
import os
import struct
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.executable_finder import ExecutableFinder
from spinn_machine import CoreSubsets, Router
from spinnman.model import ExecutableTargets
from spinnman.model.enums import CPUState
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException
from spinn_front_end_common.utilities.system_control_logic import (
    run_system_application)
from spinn_front_end_common.utilities.utility_objs import ExecutableType
logger = logging.getLogger(__name__)
_FOUR_WORDS = struct.Struct("<IIII")
_THREE_WORDS = struct.Struct("<III")
# The SDRAM Tag used by the application - note this is fixed in the APLX
_SDRAM_TAG = 1


def mundy_on_chip_router_compression(
        routing_tables, transceiver, machine, app_id,
        system_provenance_folder, compress_only_when_needed=True,
        compress_as_much_as_possible=False):
    """ Load routing tables and compress them using Mundy's algorithm.

    This uses an aplx built by Mundy which no longer compiles but still works
    with the current tool chain

    :param ~pacman.model.routing_tables.MulticastRoutingTables routing_tables:
        the memory routing tables to be compressed
    :param ~spinnman.Transceiver transceiver: the spinnman interface
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
    :return:
    """
    # pylint: disable=too-many-arguments
    binary_path = os.path.join(os.path.dirname(__file__), "rt_minimise.aplx")
    compression = Compression(
        app_id, binary_path, compress_as_much_as_possible,
        machine, system_provenance_folder, routing_tables, transceiver,
        "Running Mundy routing table compression on chip")
    compression._compress_only_when_needed = compress_only_when_needed
    compression.compress(register=0)


def pair_compression(
        routing_tables, transceiver, executable_finder,
        machine, app_id, provenance_file_path,
        compress_as_much_as_possible=True):
    """ Load routing tables and compress then using the Pair Algorithm.

    See pacman/operations/router_compressors/pair_compressor.py which is the
    exact same algorithm implemented in Python.

    :param ~pacman.model.routing_tables.MulticastRoutingTables routing_tables:
        the memory routing tables to be compressed
    :param ~spinnman.Transceiver transceiver: the spinnman interface
    :param ~spinn_utilities.executable_finder.ExecutableFinder \
            executable_finder:
    :param ~spinn_machine.Machine machine:
        the SpiNNaker machine representation
    :param int app_id: the application ID used by the main application
    :param str provenance_file_path: the path to where to write the data
    :param bool compress_as_much_as_possible:
        If False, the compressor will only reduce the table until it fits in
        the router space, otherwise it will try to reduce until it until it
        can't reduce it any more
    :param executable_finder: tracker of binaries.
     """
    # pylint: disable=too-many-arguments
    binary_path = executable_finder.get_executable_path(
        "simple_pair_compressor.aplx")
    compression = Compression(
        app_id, binary_path, compress_as_much_as_possible,
        machine, provenance_file_path, routing_tables, transceiver,
        "Running pair routing table compression on chip")
    compression.compress(register=1)

def unordered_compression(
        routing_tables, transceiver, executable_finder,
        machine, app_id, provenance_file_path,
        compress_as_much_as_possible=True):
    """ Load routing tables and compress then using the unordered Algorithm.

    To the best of our knowledge this is the same algorithm as the
    mundy_on_chip_router_compression expect this one is still buildable
    so can be maintained

    :param ~pacman.model.routing_tables.MulticastRoutingTables routing_tables:
        the memory routing tables to be compressed
    :param ~spinnman.Transceiver transceiver: the spinnman interface
    :param ~spinn_utilities.executable_finder.ExecutableFinder \
            executable_finder:
    :param ~spinn_machine.Machine machine:
        the SpiNNaker machine representation
    :param int app_id: the application ID used by the main application
    :param str provenance_file_path: the path to where to write the data
    :param bool compress_as_much_as_possible:
        If False, the compressor will only reduce the table until it fits in
        the router space, otherwise it will try to reduce until it until it
        can't reduce it any more
    :param executable_finder: tracker of binaries.
     """
    # pylint: disable=too-many-arguments
    binary_path = executable_finder.get_executable_path(
        "simple_unordered_compressor.aplx")
    compression = Compression(
        app_id, binary_path, compress_as_much_as_possible,
        machine, provenance_file_path, routing_tables, transceiver,
        "Running unordered routing table compression on chip")
    compression.compress(register=1)


class Compression(object):
    """ Compressor that uses a on chip router compressor
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
         "_transceiver",
         "_routing_tables"]

    def __init__(
            self, app_id, binary_path, compress_as_much_as_possible,
            machine, provenance_file_path, routing_tables, transceiver,
            progresses_text):
        """
        :param int app_id: the application ID used by the main application
        :param str binary_path: What
        :param bool compress_as_much_as_possible:
        :param bool compress_only_when_needed:
        :param ~spinn_machine.Machine machine:
        :param str provenance_file_path:
        :param ~pacman.model.routing_tables.MulticastRoutingTables \
                routing_tables:
        :param ~spinnman.Transceiver transceiver:
        :param str progresses_text: Text to use in progress bar
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
        self._progresses_text = progresses_text

    def compress(self, register):
        """ Apply the on-machine compression algorithm.

        :param int register: number of user register to check
        """
        # pylint: disable=too-many-arguments

        # build progress bar
        progress_bar = ProgressBar(
            len(self._routing_tables.routing_tables) * 2,
            self._progresses_text)

        self._compressor_app_id = self._transceiver.app_id_tracker.get_new_id()

        # figure size of SDRAM needed for each chip for storing the routing
        # table
        for routing_table in progress_bar.over(self._routing_tables, False):
            self._load_routing_table(routing_table)

        # load the router compressor executable
        executable_targets = self._load_executables()

        executable_finder = ExecutableFinder(binary_search_paths=[])
        read_algorithm_iobuf = True
        run_system_application(
            executable_targets, self._compressor_app_id, self._transceiver,
            self._provenance_file_path, executable_finder,
            read_algorithm_iobuf,
            functools.partial(
                self._check_for_success,
                register=register),
            [CPUState.FINISHED], False, 0,
            "compressor_on_{}_{}_{}.txt",
            [self._binary_path],
            progress_bar)

    def _load_routing_table(self, table):
        """
        :param ~.MulticastRoutingTables routing_table:
            the pacman router table instance
        """
        data = self._build_data(table)

        # go to spinnman and ask for a memory region of that size per chip.
        base_address = self._transceiver.malloc_sdram(
            table.x, table.y, len(data), self._compressor_app_id, _SDRAM_TAG)

        # write SDRAM requirements per chip
        self._transceiver.write_memory(table.x, table.y, base_address, data)

    def _check_for_success(self, executable_targets, transceiver, register):
        """ Goes through the cores checking for cores that have failed to\
            compress the routing tables to the level where they fit into the\
            router

        :param ExecutableTargets executable_targets:
        :param int register: number of user register to check
        """
        for core_subset in executable_targets.all_core_subsets:
            x = core_subset.x
            y = core_subset.y
            for p in core_subset.processor_ids:
                # Read the result from specified register
                if register == 0:
                    result = transceiver.read_user_0(x, y, p)
                elif register == 1:
                    result = transceiver.read_user_1(x, y, p)
                elif register == 2:
                    result = transceiver.read_user_2(x, y, p)
                else:
                    raise Exception("Incorrect register")
                # The result is 0 if success, otherwise failure
                if result != 0:
                    self._handle_failure(executable_targets)

                    raise SpinnFrontEndException(
                        "The router compressor on {}, {} failed to complete"
                        .format(x, y))

    def _load_executables(self):
        """ Loads the router compressor onto the chips.

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

    def _build_data(self, routing_table):
        """ Convert the router table into the data needed by the router\
            compressor c code.

        :param ~.MulticastRoutingTables routing_table:
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
                routing_table.number_of_entries)
        else:
            # Mundys compressor can not be changed so uses it own structure
            data += _FOUR_WORDS.pack(
                self._app_id, int(self._compress_only_when_needed),
                int(self._compress_as_much_as_possible),
                # Write the size of the table
                routing_table.number_of_entries)

        for entry in routing_table.multicast_routing_entries:
            data += _FOUR_WORDS.pack(
                entry.routing_entry_key, entry.mask,
                Router.convert_routing_table_entry_to_spinnaker_route(entry),
                Compression.make_source_hack(entry=entry))
        return bytearray(data)

    @staticmethod
    def make_source_hack(entry):
        """ Hack to support the source requirement for the router compressor\
            on chip

        :param ~spinn_machine.MulticastRoutingEntry entry:
            the multicast router table entry.
        :return: return the source value
        :rtype: int
        """
        if entry.defaultable:
            return (list(entry.link_ids)[0] + 3) % 6
        elif entry.link_ids:
            return list(entry.link_ids)[0]
        return 0
