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

from spinn_utilities.progress_bar import ProgressBar
from pacman.utilities.algorithm_utilities.routes_format import (
    _reduce_route_value)
from spinn_front_end_common.data import FecDataView
from .utils import csvopen


def fixed_route_from_machine_report() -> None:
    """
    Writes the fixed routes from the machine.
    """
    file_name = FecDataView.get_run_dir_file_name("fixed_route_routers.csv")
    transceiver = FecDataView.get_transceiver()
    machine = FecDataView.get_machine()
    link_labels = {0: 'E', 1: 'NE', 2: 'N', 3: 'W', 4: 'SW', 5: 'S'}

    progress = ProgressBar(machine.n_chips, "Writing fixed route report")

    app_id = FecDataView.get_app_id()
    with csvopen(file_name, "X,Y,Route,Cores,Links") as f:
        for chip in progress.over(machine.chips):
            fixed_route = transceiver.read_fixed_route(
                chip.x, chip.y, app_id)
            f.writerow([
                chip.x, chip.y, _reduce_route_value(
                    fixed_route.processor_ids, fixed_route.link_ids),
                ", ".join(
                    str(processor)
                    for processor in sorted(fixed_route.processor_ids)),
                ", ".join(
                    link_labels[link]
                    for link in sorted(fixed_route.link_ids))])
