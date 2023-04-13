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

from spinn_utilities.config_holder import get_config_int
from spinn_utilities.progress_bar import ProgressBar
from pacman.model.placements import Placement
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utility_models import (
    ChipPowerMonitorMachineVertex)

_LABEL = "chip_power_monitor_{}_vertex_for_chip({}:{})"


def insert_chip_power_monitors_to_graphs(placements):
    """
    Adds chip power monitors into a given graph.

    param Placements placements:
    """
    sampling_frequency = get_config_int("EnergyMonitor", "sampling_frequency")
    machine = FecDataView.get_machine()
    # create progress bar
    progress = ProgressBar(
        machine.n_chips, "Adding Chip power monitors to Graph")

    for chip in progress.over(machine.chips):
        vertex = ChipPowerMonitorMachineVertex(
            f"ChipPowerMonitor on {chip.x}, {chip.y}",
            sampling_frequency=sampling_frequency)
        cores = __cores(machine, chip.x, chip.y)
        p = cores[placements.n_placements_on_chip(chip.x, chip.y)]
        placements.add_placement(Placement(vertex, chip.x, chip.y, p))


def __cores(machine, x, y):
    return [p.processor_id for p in machine.get_chip_at(x, y).processors
            if not p.is_monitor]
