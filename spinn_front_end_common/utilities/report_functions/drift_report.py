# Copyright (c) 2022 The University of Manchester
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
import struct
from spinn_utilities.progress_bar import ProgressBar
from spinnman.messages.spinnaker_boot import SystemVariableDefinition
from spinn_front_end_common.utilities.globals_variables import (
    report_default_directory)
from spinn_utilities.config_holder import get_config_bool

# The fixed point position for drift readings
DRIFT_FP = 1 << 17


def drift_report(txrx):
    """ A report on the clock drift as reported by each chip
    """
    ethernet_only = get_config_bool(
            "Reports", "drift_report_ethernet_only")
    machine = txrx.get_machine_details()
    eth_chips = machine.ethernet_connected_chips
    n_chips = machine.n_chips
    if ethernet_only:
        n_chips = len(eth_chips)

    # create file path
    directory_name = os.path.join(
        report_default_directory(), "clock_drift.csv")

    # If the file is new, write a header
    if not os.path.exists(directory_name):
        with open(directory_name, "w") as writer:
            for eth_chip in eth_chips:
                if ethernet_only:
                    writer.write(f'"{eth_chip.x} {eth_chip.y}",')
                else:
                    for chip in machine.get_chips_by_ethernet(
                            eth_chip.x, eth_chip.y):
                        writer.write(f'"{chip.x} {chip.y}"')
            writer.write("\n")

    # create the progress bar for end users
    progress = ProgressBar(n_chips, "Writing clock drift report")

    # iterate over ethernet chips and then the chips on that board
    with open(directory_name, "a") as writer:
        for eth_chip in eth_chips:
            if ethernet_only:
                __write_drift(txrx, eth_chip, writer)
                progress.update()
            else:
                for chip in machine.get_chips_by_ethernet(
                        eth_chip.x, eth_chip.y):
                    __write_drift(txrx, chip, writer)
                    progress.update()
        writer.write("\n")


def __write_drift(txrx, chip, writer):
    drift = txrx._get_sv_data(
        chip.x, chip.y, SystemVariableDefinition.clock_drift)
    drift = struct.unpack("<i", struct.pack("<I", drift))[0]
    drift = drift / (1 << 17)
    writer.write(f'"{drift}",')
