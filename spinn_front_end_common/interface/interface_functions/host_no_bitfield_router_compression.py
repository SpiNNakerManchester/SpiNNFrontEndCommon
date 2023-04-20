# Copyright (c) 2017 The University of Manchester
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

import logging
import struct
from spinn_utilities.config_holder import get_config_bool
from spinn_utilities.log import FormatAdapter
from spinn_utilities.progress_bar import ProgressBar
from spinn_machine import CoreSubsets, Router
from spinnman.model import ExecutableTargets
from spinnman.model.enums import CPUState
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException
from spinn_front_end_common.utilities.system_control_logic import (
    run_system_application)
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utilities.helpful_functions import (
    get_defaultable_source_id)
from spinn_front_end_common.utilities.constants import COMPRESSOR_SDRAM_TAG
_FOUR_WORDS = struct.Struct("<IIII")
_THREE_WORDS = struct.Struct("<III")

logger = FormatAdapter(logging.getLogger(__name__))


def pair_compression():
    """
    Load routing tables and compress then using the Pair Algorithm.

    See ``pacman/operations/router_compressors/pair_compressor.py`` which is
    the exact same algorithm implemented in Python.

    :raises SpinnFrontEndException: If compression fails
     """
    # pylint: disable=too-many-arguments
    binary_path = FecDataView.get_executable_path(
        "simple_pair_compressor.aplx")
    compression = Compression(
        binary_path,
        "Running pair routing table compression on chip", result_register=1)
    compression.compress()


def ordered_covering_compression():
    """
    Load routing tables and compress then using the unordered Algorithm.

    To the best of our knowledge this is the same algorithm as
    :py:func:`mundy_on_chip_router_compression`, except this one is still
    buildable and can be maintained.

    :raises SpinnFrontEndException: If compression fails
    """
    # pylint: disable=too-many-arguments
    binary_path = FecDataView.get_executable_path(
        "simple_unordered_compressor.aplx")
    compression = Compression(
        binary_path,
        "Running unordered routing table compression on chip",
        result_register=1)
    compression.compress()


class Compression(object):
    """
    Compression algorithm implementation that uses a on-chip router
    compressor in order to parallelise.
    """

    __slots__ = [
        "_binary_path",
        "_compress_as_much_as_possible",
        "_compress_only_when_needed",
        "_compressor_app_id",
        "_progresses_text",
        "__result_register",
        "_routing_tables",
        "__failures"]

    def __init__(
            self, binary_path,  progress_text, result_register):
        """
        :param str binary_path: What binary to run
        :param ~spinn_machine.Machine machine: The machine model
        :param str progress_text: Text to use in progress bar
        :param int result_register:
            number of the user register to check for the result code
        """
        self._binary_path = binary_path
        self._compress_as_much_as_possible = get_config_bool(
            "Mapping", "router_table_compress_as_far_as_possible")
        # Only used by mundy compressor we can not rebuild
        self._compress_only_when_needed = None
        self._routing_tables = FecDataView.get_precompressed()
        self._progresses_text = progress_text
        self._compressor_app_id = None
        self.__failures = []
        self.__result_register = result_register

    def compress(self):
        """
        Apply the on-machine compression algorithm.

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

        self._compressor_app_id = FecDataView().get_new_id()

        # figure size of SDRAM needed for each chip for storing the routing
        # table
        for routing_table in progress_bar.over(self._routing_tables, False):
            self._load_routing_table(routing_table)

        # load the router compressor executable
        executable_targets = self._load_executables()

        run_system_application(
            executable_targets, self._compressor_app_id,
            get_config_bool("Reports", "write_compressor_iobuf"),
            self._check_for_success,
            [CPUState.FINISHED], False, "compressor_on_{}_{}_{}.txt",
            [self._binary_path], progress_bar)
        if self.__failures:
            raise SpinnFrontEndException(
                f"The router compressor failed on {self.__failures}")

    def _load_routing_table(self, table):
        """
        :param pacman.model.routing_tables.AbstractMulticastRoutingTable table:
            the pacman router table instance
        """
        transceiver = FecDataView.get_transceiver()
        data = self._build_data(table)

        # go to spinnman and ask for a memory region of that size per chip.
        base_address = transceiver.malloc_sdram(
            table.x, table.y, len(data), self._compressor_app_id,
            COMPRESSOR_SDRAM_TAG)

        # write SDRAM requirements per chip
        transceiver.write_memory(table.x, table.y, base_address, data)

    def _check_for_success(self, executable_targets):
        """
        Goes through the cores checking for cores that have failed to compress
        the routing tables to the level where they fit into the router.

        :param ~spinnman.model.ExecutableTargets executable_targets:
        """
        transceiver = FecDataView.get_transceiver()
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
                    raise ValueError(
                        "Incorrect register {self.__result_register}")
                # The result is 0 if success, otherwise failure
                if result != 0:
                    self.__failures.append((x, y))
        return len(self.__failures) == 0

    def _load_executables(self):
        """
        Plans the loading of the router compressor onto the chips.

        :return:
            the executable targets that represent all cores/chips which have
            active routing tables
        :rtype: ~spinnman.model.ExecutableTargets
        """
        # build core subsets
        core_subsets = CoreSubsets()
        for routing_table in self._routing_tables:
            # get the first none monitor core
            chip = FecDataView.get_chip_at(routing_table.x, routing_table.y)
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
        """
        Convert the router table into the data needed by the router
        compressor C code.

        :param table: the PACMAN router table instance
        :type table: ~pacman.model.routing_tables.AbstractMulticastRoutingTable
        :return: The byte array of data
        :rtype: bytearray
        """
        # write header data of the app ID to load the data, if to store
        # results in SDRAM and the router table entries

        data = b''
        if self._compress_only_when_needed is None:
            data += _THREE_WORDS.pack(
                FecDataView.get_app_id(),
                int(self._compress_as_much_as_possible),
                # Write the size of the table
                table.number_of_entries)
        else:
            # Mundy's compressor can not be changed so uses it own structure
            data += _FOUR_WORDS.pack(
                FecDataView.get_app_id(),
                int(self._compress_only_when_needed),
                int(self._compress_as_much_as_possible),
                # Write the size of the table
                table.number_of_entries)

        for entry in table.multicast_routing_entries:
            data += _FOUR_WORDS.pack(
                entry.routing_entry_key, entry.mask,
                Router.convert_routing_table_entry_to_spinnaker_route(entry),
                get_defaultable_source_id(entry))
        return bytearray(data)
