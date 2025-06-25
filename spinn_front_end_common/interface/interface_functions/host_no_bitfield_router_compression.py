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
from typing import List
from spinn_utilities.config_holder import get_config_bool
from spinn_utilities.log import FormatAdapter
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.typing.coords import XY
from spinn_machine import CoreSubsets, Router
from spinnman.model import ExecutableTargets
from spinnman.model.enums import CPUState, ExecutableType, UserRegister
from pacman.model.routing_tables import AbstractMulticastRoutingTable
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException
from spinn_front_end_common.utilities.system_control_logic import (
    run_system_application)
from spinn_front_end_common.utilities.helpful_functions import (
    get_defaultable_source_id)
from spinn_front_end_common.utilities.constants import COMPRESSOR_SDRAM_TAG

_FOUR_WORDS = struct.Struct("<IIII")
_THREE_WORDS = struct.Struct("<III")
logger = FormatAdapter(logging.getLogger(__name__))


def pair_compression() -> None:
    """
    Load routing tables and compress then using the Pair Algorithm.

    See ``pacman/operations/router_compressors/pair_compressor.py`` which is
    the exact same algorithm implemented in Python.

    :raises SpinnFrontEndException: If compression fails
     """
    compression = Compression(
        FecDataView.get_executable_path("simple_pair_compressor.aplx"),
        "Running pair routing table compression on chip",
        result_register=UserRegister.USER_1)
    compression.compress()


def ordered_covering_compression() -> None:
    """
    Load routing tables and compress then using the unordered Algorithm.

    To the best of our knowledge this is the same algorithm as
    :py:func:`mundy_on_chip_router_compression`, except this one is still
    buildable and can be maintained.

    :raises SpinnFrontEndException: If compression fails
    """
    compression = Compression(
        FecDataView.get_executable_path("simple_unordered_compressor.aplx"),
        "Running unordered routing table compression on chip",
        result_register=UserRegister.USER_1)
    compression.compress()


class Compression(object):
    """
    Compression algorithm implementation that uses a on-chip router
    compressor in order to parallelise.
    """
    __slots__ = (
        "_binary_path",
        "_compress_as_much_as_possible",
        "_compress_only_when_needed",
        "_compressor_app_id",
        "_progresses_text",
        "__result_register",
        "_routing_tables",
        "__failures")

    def __init__(
            self, binary_path: str, progress_text: str,
            result_register: UserRegister):
        """
        :param binary_path: What binary to run
        :param progress_text: Text to use in progress bar
        :param result_register:
            number of the user register to check for the result code
        """
        self._binary_path = binary_path
        self._compress_as_much_as_possible = get_config_bool(
            "Mapping", "router_table_compress_as_far_as_possible")
        # Only used by Mundy compressor we can not rebuild
        self._compress_only_when_needed = None
        self._routing_tables = FecDataView.get_precompressed()
        self._progresses_text = progress_text
        self._compressor_app_id = -1
        self.__failures: List[XY] = []
        self.__result_register = result_register

    def compress(self) -> None:
        """
        Apply the on-machine compression algorithm.

        :raises SpinnFrontEndException: If compression fails
        """
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
            get_config_bool("Reports", "write_compressor_iobuf") or False,
            self._check_for_success, frozenset([CPUState.FINISHED]), False,
            "compressor_on_{}_{}_{}.txt", [self._binary_path], progress_bar)
        if self.__failures:
            raise SpinnFrontEndException(
                f"The router compressor failed on {self.__failures}")

    def _load_routing_table(
            self, table: AbstractMulticastRoutingTable) -> None:
        """
        :param table: the router table to load
        """
        transceiver = FecDataView.get_transceiver()
        data = self._build_data(table)

        # go to spinnman and ask for a memory region of that size per chip.
        base_address = transceiver.malloc_sdram(
            table.x, table.y, len(data), self._compressor_app_id,
            COMPRESSOR_SDRAM_TAG)

        # write SDRAM requirements per chip
        transceiver.write_memory(table.x, table.y, base_address, data)

    def _check_for_success(
            self, executable_targets: ExecutableTargets) -> bool:
        """
        Goes through the cores checking for cores that have failed to compress
        the routing tables to the level where they fit into the router.

        :param executable_targets:
        """
        transceiver = FecDataView.get_transceiver()
        for core_subset in executable_targets.all_core_subsets:
            x, y = core_subset.x, core_subset.y
            for p in core_subset.processor_ids:
                # Read the result from specified register
                result = transceiver.read_user(x, y, p, self.__result_register)
                # The result is 0 if success, otherwise failure
                if result != 0:
                    self.__failures.append((x, y))
        return len(self.__failures) == 0

    def _load_executables(self) -> ExecutableTargets:
        """
        Plans the loading of the router compressor onto the chips.

        :return:
            the executable targets that represent all cores/chips which have
            active routing tables
        """
        # build core subsets
        core_subsets = CoreSubsets()
        for routing_table in self._routing_tables.routing_tables:
            # add to the core subsets
            core_subsets.add_processor(
                routing_table.x, routing_table.y,
                routing_table.chip.placable_processors_ids[0])

        # build executable targets
        executable_targets = ExecutableTargets()
        executable_targets.add_subsets(self._binary_path, core_subsets,
                                       ExecutableType.SYSTEM)

        return executable_targets

    def _build_data(self, table: AbstractMulticastRoutingTable) -> bytes:
        """
        Convert the router table into the data needed by the router
        compressor C code.

        :param table: the PACMAN router table instance
        :return: The byte array of data
        """
        # write header data of the app ID to load the data, if to store
        # results in SDRAM and the router table entries

        data = b''
        if self._compress_only_when_needed is None:
            data += _THREE_WORDS.pack(
                FecDataView.get_app_id(),
                int(self._compress_as_much_as_possible or False),
                # Write the size of the table
                table.number_of_entries)
        else:
            # Mundy compressor can not be changed so uses it own structure
            data += _FOUR_WORDS.pack(
                FecDataView.get_app_id(),
                int(self._compress_only_when_needed),
                int(self._compress_as_much_as_possible),
                # Write the size of the table
                table.number_of_entries)

        for entry in table.multicast_routing_entries:
            data += _FOUR_WORDS.pack(
                entry.key, entry.mask,
                Router.convert_routing_table_entry_to_spinnaker_route(entry),
                get_defaultable_source_id(entry))
        return bytearray(data)
