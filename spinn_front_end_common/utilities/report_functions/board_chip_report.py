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
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.utilities.globals_variables import (
    report_default_directory)

AREA_CODE_REPORT_NAME = "board_chip_report.txt"


def board_chip_report(machine):
    """ Creates a report that states where in SDRAM each region is.

    :param ~spinn_machine.Machine machine:
        python representation of the machine
    :rtype: None
    """

    # create file path
    directory_name = os.path.join(
        report_default_directory(), AREA_CODE_REPORT_NAME)

    # create the progress bar for end users
    progress_bar = ProgressBar(
        len(machine.ethernet_connected_chips),
        "Writing the board chip report")

    # iterate over ethernet chips and then the chips on that board
    with open(directory_name, "w", encoding="utf-8") as writer:
        _write_report(writer, machine, progress_bar)


def _write_report(writer, machine, progress_bar):
    """
    :param ~io.FileIO writer:
    :param ~spinn_machine.Machine machine:
    :param ~spinn_utilities.progress_bar.ProgressBar progress_bar:
    """
    for e_chip in progress_bar.over(machine.ethernet_connected_chips):
        xyps = [f"({chip.x}, {chip.y}, P: {chip.get_physical_core_id(0)})"
                for chip in machine.get_chips_by_ethernet(e_chip.x, e_chip.y)]

        writer.write(
            "board with IP address : {} : has chips [{}]\n".format(
                e_chip.ip_address, ", ".join(xyps)))
