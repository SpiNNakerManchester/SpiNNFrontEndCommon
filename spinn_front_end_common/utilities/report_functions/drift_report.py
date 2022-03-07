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

# The fixed point position for drift readings
DRIFT_FP = 1 << 17


def drift_report(txrx, ethernet_only=True):
    """ A report on the clock drift as reported by each chip
    """
    machine = txrx.get_machine_details()
    chips = machine.chips
    if ethernet_only:
        chips = machine.ethernet_connected_chips

    # create file path
    directory_name = os.path.join(
        report_default_directory(), "clock_drift.csv")

    # If the file is new, write a header
    if not os.path.exists(directory_name):
        with open(directory_name, "w") as writer:
            for chip in chips:
                writer.write(f'"{chip.x}-{chip.y}",')
            writer.write("\n")

    # create the progress bar for end users
    progress = ProgressBar(len(chips), "Writing clock drift report")

    # iterate over ethernet chips and then the chips on that board
    with open(directory_name, "wa") as writer:
        for chip in progress.over(chips):
            drift = txrx._get_sv_data(
                chip.x, chip.y, SystemVariableDefinition.clock_drift)
            drift = struct.unpack("<i", struct.pack("<I", drift))[0]
            drift = drift / (1 << 17)
            writer.write(f'"{drift}",')
        writer.write("\n")
