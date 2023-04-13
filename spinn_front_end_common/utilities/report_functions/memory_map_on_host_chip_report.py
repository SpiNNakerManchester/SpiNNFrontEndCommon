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
import os
import struct
from spinn_utilities.log import FormatAdapter
from spinn_utilities.progress_bar import ProgressBar
from data_specification.constants import MAX_MEM_REGIONS
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.constants import BYTES_PER_WORD

logger = FormatAdapter(logging.getLogger(__name__))
_ONE_WORD = struct.Struct("<I")
REGION_HEADER_SIZE = 2 * BYTES_PER_WORD


def memory_map_on_host_chip_report():
    """
    Report on memory usage. Creates a report that states where in SDRAM
    each region is (read from machine).
    """
    directory_name = os.path.join(
        FecDataView.get_run_dir_path(), "memory_map_reports")
    if not os.path.exists(directory_name):
        os.makedirs(directory_name)

    transceiver = FecDataView.get_transceiver()
    dsg_targets = FecDataView.get_dsg_targets()
    progress = ProgressBar(
        dsg_targets.ds_n_cores(), "Writing memory map reports")
    for (x, y, p) in progress.over(dsg_targets.keys()):
        file_name = os.path.join(
            directory_name, f"memory_map_from_processor_{x}_{y}_{p}.txt")
        try:
            with open(file_name, "w", encoding="utf-8") as f:
                _describe_mem_map(f, transceiver, x, y, p)
        except IOError:
            logger.exception(
                "Generate_placement_reports: Can't open file {} for writing.",
                file_name)


def _describe_mem_map(f, txrx, x, y, p):
    """
    :param ~spinnman.transceiver.Transceiver txrx:
    """
    # Read the memory map data from the given core
    region_table_addr = _get_region_table_addr(txrx, x, y, p)
    memmap_data = txrx.read_memory(
        x, y, region_table_addr, BYTES_PER_WORD * MAX_MEM_REGIONS)

    # Convert the map to a human-readable description
    f.write("On chip data specification executor\n\n")
    for i in range(MAX_MEM_REGIONS):
        region_address, = _ONE_WORD.unpack_from(
            memmap_data, i * BYTES_PER_WORD)
        f.write(f"Region {i:d}:\n\t start address: 0x{region_address:x}\n\n")


def _get_region_table_addr(txrx, x, y, p):
    """
    :param ~spinnman.transceiver.Transceiver txrx:
    """
    user_0_addr = txrx.get_user_0_register_address_from_core(p)
    return txrx.read_word(x, y, user_0_addr) + REGION_HEADER_SIZE
