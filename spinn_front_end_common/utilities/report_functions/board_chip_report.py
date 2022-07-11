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
from spinn_machine import Machine, Router
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
    down_links = list()
    down_chips = list()
    down_cores = list()
    for e_chip in progress_bar.over(machine.ethernet_connected_chips):
        existing_chips = list()
        for l_x, l_y in machine.local_xys:
            x, y = machine.get_global_xy(l_x, l_y, e_chip.x, e_chip.y)
            if machine.is_chip_at(x, y):
                chip = machine.get_chip_at(x, y)
                existing_chips.append(
                    f"({x}, {y}, P: {chip.get_physical_core_id(0)})")
                down_procs = set(range(Machine.DEFAULT_MAX_CORES_PER_CHIP))
                for proc in chip.processors:
                    down_procs.remove(proc.processor_id)
                for p in down_procs:
                    phys_p = chip.get_physical_core_id(p)
                    core = p
                    if phys_p is not None:
                        core = -phys_p
                    down_cores.append((l_x, l_y, core, e_chip.ip_address))
            else:
                down_chips.append((l_x, l_y, e_chip.ip_address))
            for link in range(Router.MAX_LINKS_PER_ROUTER):
                if not machine.is_link_at(x, y, link):
                    down_links.append((l_x, l_y, link, e_chip.ip_address))

        existing_chips = ", ".join(existing_chips)
        writer.write(
            f"board with IP address: {e_chip.ip_address} has chips"
            f" {existing_chips}\n")

    down_chips_out = ":".join(
        f"{x},{y},{ip}" for x, y, ip in down_chips)
    down_cores_out = ":".join(
        f"{x},{y},{p},{ip}" for x, y, p, ip in down_cores)
    down_links_out = ":".join(
        f"{x},{y},{l},{ip}" for x, y, l, ip in down_links)
    writer.write(f"Down chips: {down_chips_out}\n")
    writer.write(f"Down cores: {down_cores_out}\n")
    writer.write(f"Down Links: {down_links_out}\n")


def _get_local_xy(self, chip):
    local_x = ((chip.x - chip.nearest_ethernet_x + self._width)
               % self._width)
    local_y = ((chip.y - chip.nearest_ethernet_y + self._height)
               % self._height)
    return local_x, local_y
