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
import logging
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.config_holder import get_config_bool
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.utility_calls import csvopen

# The fixed point position for drift readings
CLOCK_DRIFT_REPORT = "clock_drift.csv"

logger = FormatAdapter(logging.getLogger(__name__))


def drift_report():
    """
    A report on the clock drift as reported by each chip
    """
    if get_config_bool("Reports", "drift_report_ethernet_only"):
        _ethernet_drift_report()
    else:
        _all_drift_report()


def _ethernet_drift_report():
    """
    A report on the clock drift as reported by each ethernet chip
    """
    machine = FecDataView.get_machine()
    txrx = FecDataView.get_transceiver()

    # create file path
    file_name = FecDataView.get_run_dir_file_name(CLOCK_DRIFT_REPORT)

    # If the file is new, write a header
    if not os.path.exists(file_name):
        with csvopen(file_name, None) as writer:
            writer.writerow(
                f"{eth_chip.x} {eth_chip.y}"
                for eth_chip in machine.ethernet_connected_chips)

    # create the progress bar for end users
    progress = ProgressBar(
        len(machine.ethernet_connected_chips), "Writing clock drift report")

    # iterate over ethernet chips and then the chips on that board
    with csvopen(file_name, None, mode="a") as writer:
        writer.writerow(
            txrx.get_clock_drift(eth_chip.x, eth_chip.y)
            for eth_chip in progress.over(machine.ethernet_connected_chips))


def _all_drift_report():
    """
    A report on the clock drift as reported by all chips
    """
    machine = FecDataView.get_machine()
    txrx = FecDataView.get_transceiver()

    # create file path
    file_name = FecDataView.get_run_dir_file_name(CLOCK_DRIFT_REPORT)

    # If the file is new, write a header
    if not os.path.exists(file_name):
        with csvopen(file_name, None) as writer:
            writer.writerow(
                f"{chip.x} {chip.y}"
                for ec in machine.ethernet_connected_chips
                for chip in machine.get_chips_by_ethernet(ec.x, ec.y))

    # create the progress bar for end users
    progress = ProgressBar(machine.n_chips, "Writing clock drift report")

    # iterate over ethernet chips and then the chips on that board
    with csvopen(file_name, None, mode="a") as writer:
        for eth_chip in machine.ethernet_connected_chips:
            drifts = []
            last_drift = None
            for chip in progress.over(machine.get_chips_by_ethernet(
                    eth_chip.x, eth_chip.y), finish_at_end=False):
                drift = txrx.get_clock_drift(chip.x, chip.y)
                drifts.append(drift)
                if last_drift is None:
                    last_drift = drift
                elif last_drift != drift:
                    logger.warning(
                        "On board {}, chip {}, {} is not in sync ({} vs {})",
                        eth_chip.ip_address, chip.x, chip.y, drift, last_drift)
            writer.writerow(drifts)
        progress.end()
