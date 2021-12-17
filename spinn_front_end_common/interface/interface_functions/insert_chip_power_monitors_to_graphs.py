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

from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.utility_models import ChipPowerMonitorMachineVertex
from pacman.model.placements import Placement

_LABEL = "chip_power_monitor_{}_vertex_for_chip({}:{})"


def insert_chip_power_monitors_to_graphs(
        machine, sampling_frequency, placements):
    """ Adds chip power monitors into a given graph.

    :param ~spinn_machine.Machine machine:
        the SpiNNaker machine as discovered
    :param int sampling_frequency:
    :param Placements placements:
    """

    # create progress bar
    progress = ProgressBar(
        machine.n_chips, "Adding Chip power monitors to Graph")

    for chip in progress.over(machine.chips):
        if not chip.virtual:
            vertex = ChipPowerMonitorMachineVertex(
                f"ChipPowerMonitor on {chip.x}, {chip.y}", [],
                sampling_frequency=sampling_frequency)
            p = placements.n_placements_on_chip(chip.x, chip.y) + 1
            placements.add_placement(Placement(vertex, chip.x, chip.y, p))
