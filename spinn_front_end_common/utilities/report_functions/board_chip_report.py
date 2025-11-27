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
    n_cores = FecDataView.get_machine_version().max_cores_per_chip
    n_links = Router.MAX_LINKS_PER_ROUTER
    cores = set(range(n_cores))
    for e_chip in progress_bar.over(machine.ethernet_connected_chips):
        writer.write(
            f"board with IP address: {e_chip.ip_address}\n")
        for l_x, l_y in machine.local_xys:
            down_chips: List[Tuple[int, int]] = list()
            x, y = machine.get_global_xy(l_x, l_y, e_chip.x, e_chip.y)
            if machine.is_chip_at(x, y):
                chip = machine[x, y]
                writer.write(f"\t{x}, {y}, scamp core 0:"
                    f"{FecDataView.get_physical_string(chip, 0)}\n")

                if chip.n_processors < n_cores:
                    physical = FecDataView.get_physical_cores(chip)
                    down_cores = list(cores - physical)
                    down_cores.sort()
                    writer.write(f"\t\tDown Cores: {down_cores}\n")

                router = chip.router
                if len(router) < n_links:
                    down_links = list()
                    for link in range(n_links):
                        if chip.router.is_link(link):
                            continue
                        tx, ty = machine.xy_over_link(x, y, link)
                        if machine.is_chip_at(tx, ty):
                            down_links.append(link)
                    if down_links:
                        writer.write(f"\t\tDown Links: {down_links}\n")
            else:
                down_chips.append((x, y))

        if down_chips:
            writer.write(f"\t\tDown chips: {down_chips}\n")
