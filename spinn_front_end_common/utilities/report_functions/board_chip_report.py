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

from typing import List, TextIO, Tuple

from spinn_utilities.config_holder import get_report_path
from spinn_utilities.progress_bar import ProgressBar

from spinn_machine import Machine, Router

from spinn_front_end_common.data import FecDataView


def board_chip_report() -> None:
    """
    Creates a report that states where in SDRAM each region is.
    """
    machine = FecDataView.get_machine()
    # create file path
    directory_name = get_report_path("path_board_chip_report")
    # create the progress bar for end users
    progress_bar = ProgressBar(
        len(machine.ethernet_connected_chips),
        "Writing the board chip report")

    # iterate over Ethernet chips and then the chips on that board
    with open(directory_name, "w", encoding="utf-8") as writer:
        _write_report(writer, machine, progress_bar)


def _write_report(
        writer: TextIO, machine: Machine, progress_bar: ProgressBar) -> None:
    down_links: List[Tuple[int, int, int, str]] = []
    down_chips: List[Tuple[int, int, str]] = []
    down_cores: List[Tuple[int, int, str, str]] = []
    for e_chip in progress_bar.over(machine.ethernet_connected_chips):
        assert e_chip.ip_address is not None
        existing_chips: List[str] = []
        for l_x, l_y in machine.local_xys:
            x, y = machine.get_global_xy(l_x, l_y, e_chip.x, e_chip.y)
            if machine.is_chip_at(x, y):
                chip = machine[x, y]
                existing_chips.append(
                    f"({x}, {y}, "
                    f"{FecDataView.get_physical_string((x, y), 0)})")
                n_cores = FecDataView.get_machine_version().max_cores_per_chip
                down_procs = set(range(n_cores))
                for p in chip.all_processor_ids:
                    down_procs.remove(p)
                for p in down_procs:
                    phys_p = FecDataView.get_physical_string((x, y), p)
                    if not phys_p:   # ""
                        phys_p = str(-p)
                    down_cores.append((l_x, l_y, phys_p, e_chip.ip_address))
            else:
                down_chips.append((l_x, l_y, e_chip.ip_address))
            for link in range(Router.MAX_LINKS_PER_ROUTER):
                if not machine.is_link_at(x, y, link):
                    down_links.append((l_x, l_y, link, e_chip.ip_address))

        writer.write(
            f"board with IP address: {e_chip.ip_address} has chips"
            f" {', '.join(existing_chips)}\n")

    down_chips_out = ":".join(
        f"{x},{y},{ip}" for x, y, ip in down_chips)
    down_cores_out = ":".join(
        f"{x},{y},{phys_p},{ip}" for x, y, phys_p, ip in down_cores)
    down_links_out = ":".join(
        f"{x},{y},{l},{ip}" for x, y, l, ip in down_links)
    writer.write(f"Down chips: {down_chips_out}\n")
    writer.write(f"Down cores: {down_cores_out}\n")
    writer.write(f"Down Links: {down_links_out}\n")
