# Copyright (c) 2022 The University of Manchester
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
import os
import struct
import logging
from typing import TextIO
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.config_holder import get_config_bool
from spinn_utilities.log import FormatAdapter
from spinn_machine import Chip
from spinnman.messages.spinnaker_boot import SystemVariableDefinition
from spinnman.transceiver import Transceiver
from spinn_front_end_common.data import FecDataView

# The fixed point position for drift readings
DRIFT_FP = 1 << 17
CLOCK_DRIFT_REPORT = "clock_drift.csv"

logger = FormatAdapter(logging.getLogger(__name__))


def drift_report() -> None:
    """
    A report on the clock drift as reported by each chip
    """
    ethernet_only = get_config_bool("Reports", "drift_report_ethernet_only")
    machine = FecDataView.get_machine()
    eth_chips = machine.ethernet_connected_chips
    n_chips = len(eth_chips) if ethernet_only else machine.n_chips

    # create file path
    directory_name = os.path.join(
        FecDataView.get_run_dir_path(), CLOCK_DRIFT_REPORT)

    # If the file is new, write a header
    if not os.path.exists(directory_name):
        with open(directory_name, "w", encoding="utf-8") as writer:
            for eth_chip in eth_chips:
                if ethernet_only:
                    writer.write(f'"{eth_chip.x} {eth_chip.y}",')
                else:
                    for chip in machine.get_chips_by_ethernet(
                            eth_chip.x, eth_chip.y):
                        writer.write(f'"{chip.x} {chip.y}",')
            writer.write("\n")

    # create the progress bar for end users
    with ProgressBar(n_chips, "Writing clock drift report") as progress:
        # iterate over ethernet chips and then the chips on that board
        txrx = FecDataView.get_transceiver()
        with open(directory_name, "a", encoding="utf-8") as writer:
            if ethernet_only:
                for eth_chip in progress.over(eth_chips):
                    __write_drift(txrx, eth_chip, writer)
            else:
                for eth_chip in eth_chips:
                    last_drift = None
                    for chip in progress.over(machine.get_chips_by_ethernet(
                            eth_chip.x, eth_chip.y), finish_at_end=False):
                        drift = __write_drift(txrx, chip, writer)
                        if last_drift is None:
                            last_drift = drift
                        elif last_drift != drift:
                            logger.warning(
                                "On board {}, chip {}, {} is not in sync"
                                " ({} vs {})",
                                eth_chip.ip_address, chip.x, chip.y,
                                drift, last_drift)
            writer.write("\n")


def __write_drift(txrx: Transceiver, chip: Chip, writer: TextIO):
    # pylint: disable=protected-access
    drift = txrx._get_sv_data(
        chip.x, chip.y, SystemVariableDefinition.clock_drift)
    # Swap endianness!
    drift_i = struct.unpack("<i", struct.pack("<I", drift))[0]
    # Convert from unusual fixed-point format
    drift_f = drift_i / (1 << 17)
    writer.write(f'"{drift_f}",')
    return drift_f
