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

from spinn_utilities.config_holder import get_config_int
from spinn_utilities.progress_bar import ProgressBar
from pacman.model.constraints.placer_constraints import ChipAndCoreConstraint
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utility_models import (
    ChipPowerMonitor, ChipPowerMonitorMachineVertex)

_LABEL = "chip_power_monitor_{}_vertex_for_chip({}:{})"


def insert_chip_power_monitors_to_graphs():
    """ Adds chip power monitor vertices on Ethernet connected chips as\
        required.
    """
    if FecDataView().runtime_graph.n_vertices > 0:
        __add_app()
    else:
        __add_mach_only()


def __add_app():
    machine = FecDataView.get_machine()
    # create progress bar
    progress = ProgressBar(
        machine.n_chips, "Adding Chip power monitors to Graph")

    sampling_frequency = get_config_int("EnergyMonitor", "sampling_frequency")
    app_vertex = ChipPowerMonitor(
        label="ChipPowerMonitor",
        sampling_frequency=sampling_frequency)
    FecDataView().runtime_graph.add_vertex(app_vertex)
    machine_graph = FecDataView().runtime_machine_graph
    for chip in progress.over(machine.chips):
        if not chip.virtual:
            machine_graph.add_vertex(app_vertex.create_machine_vertex(
                vertex_slice=None, resources_required=None,
                label=_LABEL.format("machine", chip.x, chip.y),
                constraints=[ChipAndCoreConstraint(chip.x, chip.y)]))


def __add_mach_only():
    machine = FecDataView.get_machine()
    # create progress bar
    progress = ProgressBar(
        machine.n_chips, "Adding Chip power monitors to Graph")
    machine_graph = FecDataView().runtime_machine_graph
    sampling_frequency = get_config_int("EnergyMonitor", "sampling_frequency")
    for chip in progress.over(machine.chips):
        if not chip.virtual:
            machine_graph.add_vertex(ChipPowerMonitorMachineVertex(
                label=_LABEL.format("machine", chip.x, chip.y),
                constraints=[ChipAndCoreConstraint(chip.x, chip.y)],
                app_vertex=None,
                sampling_frequency=sampling_frequency))
