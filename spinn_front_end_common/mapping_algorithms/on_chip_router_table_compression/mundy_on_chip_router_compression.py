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

import os
from spinn_front_end_common.mapping_algorithms import (
    on_chip_router_table_compression)
from .abstract_compression import AbstractCompression


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
        :type transceiver: :py:class:`~spinnman.Transceiver`
        :param machine: the SpiNNaker machine representation
        :param app_id: the application ID used by the main application
        :param provenance_file_path: the path to where to write the data
        :return: flag stating routing compression and loading has been done
        """
        # pylint: disable=too-many-arguments

        self._compress(routing_tables, transceiver,
                       machine, app_id, provenance_file_path, _BINARY_PATH,
                       compress_only_when_needed, compress_as_much_as_possible)
