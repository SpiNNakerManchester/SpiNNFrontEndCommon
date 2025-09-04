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
from pacman.model.placements import Placement, Placements
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utility_models import (
    ChipPowerMonitorMachineVertex)
from spinn_front_end_common.utilities.utility_calls import (
    pick_core_for_system_placement)


def sample_chip_power_monitor() -> ChipPowerMonitorMachineVertex:
    """
    Creates an unplaced sample of the Vertex's used.

    This vertex should only be used for size estimates.

    :returns: An unused power monitor vertex.
    """
    return ChipPowerMonitorMachineVertex(
        "Sample ChipPowerMonitorMachineVertex")


def insert_chip_power_monitors_to_graphs(placements: Placements) -> None:
    """
    Adds chip power monitors into a given graph.

    :param placements:
    """
    machine = FecDataView.get_machine()
    # create progress bar
    progress = ProgressBar(
        machine.n_chips, "Adding Chip power monitors to Graph")

    for chip in progress.over(machine.chips):
        vertex = ChipPowerMonitorMachineVertex(
            f"ChipPowerMonitor on {chip.x}, {chip.y}")
        p = pick_core_for_system_placement(placements, chip)
        placements.add_placement(Placement(vertex, chip.x, chip.y, p))
