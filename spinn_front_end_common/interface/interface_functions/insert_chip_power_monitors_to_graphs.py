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
from pacman.model.constraints.placer_constraints import ChipAndCoreConstraint
from spinn_front_end_common.utility_models import (
    ChipPowerMonitor, ChipPowerMonitorMachineVertex)

_LABEL = "chip_power_monitor_{}_vertex_for_chip({}:{})"


class InsertChipPowerMonitorsToGraphs(object):
    """ Adds chip power monitors into a given graph.
    """

    def __call__(
            self, machine, machine_graph, n_samples_per_recording,
            sampling_frequency, application_graph=None):
        """ Adds chip power monitor vertices on Ethernet connected chips as\
            required.

        :param ~spinn_machine.Machine machine:
            the SpiNNaker machine as discovered
        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
            the machine graph
        :param int n_samples_per_recording:
        :param int sampling_frequency:
        :param application_graph: the application graph
        :type application_graph:
            ~pacman.model.graphs.application.ApplicationGraph
        """
        # pylint: disable=too-many-arguments

        # create progress bar
        progress = ProgressBar(
            machine.n_chips, "Adding Chip power monitors to Graph")

        if application_graph is not None:
            self.__add_app(
                application_graph, machine_graph, machine,
                n_samples_per_recording, sampling_frequency, progress)
        else:
            self.__add_mach_only(
                machine_graph, machine,
                n_samples_per_recording, sampling_frequency, progress)

    @staticmethod
    def __add_app(
            application_graph, machine_graph, machine, n_samples_per_recording,
            sampling_frequency, progress):
        app_vertex = ChipPowerMonitor(
            label="ChipPowerMonitor",
            sampling_frequency=sampling_frequency,
            n_samples_per_recording=n_samples_per_recording)
        application_graph.add_vertex(app_vertex)
        for chip in progress.over(machine.chips):
            if not chip.virtual:
                machine_graph.add_vertex(app_vertex.create_machine_vertex(
                    vertex_slice=None, resources_required=None,
                    label=_LABEL.format("machine", chip.x, chip.y),
                    constraints=[ChipAndCoreConstraint(chip.x, chip.y)]))

    @staticmethod
    def __add_mach_only(
            machine_graph, machine, n_samples_per_recording,
            sampling_frequency, progress):
        for chip in progress.over(machine.chips):
            if not chip.virtual:
                machine_graph.add_vertex(ChipPowerMonitorMachineVertex(
                    label=_LABEL.format("machine", chip.x, chip.y),
                    constraints=[ChipAndCoreConstraint(chip.x, chip.y)],
                    app_vertex=None,
                    sampling_frequency=sampling_frequency,
                    n_samples_per_recording=n_samples_per_recording))
