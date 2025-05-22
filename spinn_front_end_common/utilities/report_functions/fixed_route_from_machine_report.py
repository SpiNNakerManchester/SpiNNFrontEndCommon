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

from typing import Iterable
from spinn_utilities.config_holder import get_report_path
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.data import FecDataView


def fixed_route_from_machine_report() -> None:
    """
    Writes the fixed routes from the machine.
    """
    file_name = get_report_path("path_fixed_routes_report")
    transceiver = FecDataView.get_transceiver()
    machine = FecDataView.get_machine()

    progress = ProgressBar(machine.n_chips, "Writing fixed route report")

    app_id = FecDataView.get_app_id()
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(" x    y       route         [cores][links]\n")
        for chip in progress.over(machine.chips):
            fixed_route = transceiver.read_fixed_route(
                chip.x, chip.y, app_id)
            rd = _reduce_route_value(fixed_route.processor_ids,
                                     fixed_route.link_ids)
            ep = _expand_route_value(fixed_route.processor_ids,
                                     fixed_route.link_ids)
            f.write(f"{chip.x:<3}:{chip.y:<3} contains route {rd:<10} {ep}\n")


def _reduce_route_value(
        processors_ids: Iterable[int], link_ids: Iterable[int]) -> str:
    value = 0
    for link in link_ids:
        value += 1 << link
    for processor in processors_ids:
        value += 1 << (processor + 6)
    return str(value)


def _expand_route_value(
        processors_ids: Iterable[int], link_ids: Iterable[int]) -> str:
    """
    Convert a 32-bit route word into a string which lists the target
    cores and links.
    """
    route_string = "["

    # Convert processor targets to readable values:
    route_string += ", ".join(
        str(processor) for processor in sorted(processors_ids))

    route_string += "] ["

    # Convert link targets to readable values:
    link_labels = {0: 'E', 1: 'NE', 2: 'N', 3: 'W', 4: 'SW', 5: 'S'}
    route_string += ", ".join(
        link_labels[link] for link in sorted(link_ids))

    route_string += "]"
    return route_string
