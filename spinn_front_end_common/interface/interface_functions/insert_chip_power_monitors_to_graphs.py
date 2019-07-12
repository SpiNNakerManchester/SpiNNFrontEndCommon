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
from pacman.model.graphs.common import Slice
from pacman.model.constraints.placer_constraints import ChipAndCoreConstraint
from spinn_front_end_common.utility_models import (
    ChipPowerMonitor, ChipPowerMonitorMachineVertex)

_LABEL = "chip_power_monitor_{}_vertex_for_chip({}:{})"


class InsertChipPowerMonitorsToGraphs(object):
    """ Adds chip power monitors into a given graph.
    """

    def __call__(
            self, machine, machine_graph, n_samples_per_recording,
            sampling_frequency, application_graph=None, graph_mapper=None):
        """ Adds chip power monitor vertices on Ethernet connected chips as\
            required.

        :param machine: the SpiNNaker machine as discovered
        :param application_graph: the application graph
        :param machine_graph: the machine graph
        :return: mapping between LPG parameters and LPG vertex
        """
        # pylint: disable=too-many-arguments

        # create progress bar
        progress = ProgressBar(
            machine.n_chips, "Adding Chip power monitors to Graph")

        for chip in progress.over(machine.chips):
            self._add_power_monitor_for_chip(
                chip, machine_graph, application_graph, graph_mapper,
                sampling_frequency, n_samples_per_recording)

    @staticmethod
    def _add_power_monitor_for_chip(
            chip, machine_graph, application_graph, graph_mapper,
            sampling_frequency, n_samples_per_recording):
        # build constraint
        constraint = ChipAndCoreConstraint(chip.x, chip.y)

        # build machine vert
        machine_vertex = ChipPowerMonitorMachineVertex(
            label=_LABEL.format("machine", chip.x, chip.y),
            sampling_frequency=sampling_frequency,
            n_samples_per_recording=n_samples_per_recording,
            constraints=[constraint])

        # add vert to graph
        machine_graph.add_vertex(machine_vertex)

        # deal with app graphs if needed
        if application_graph is not None:

            # build app vertex
            vertex_slice = Slice(0, 0)
            application_vertex = ChipPowerMonitor(
                label=_LABEL.format("application", chip.x, chip.y),
                constraints=[constraint],
                sampling_frequency=sampling_frequency,
                n_samples_per_recording=n_samples_per_recording)

            # add to graph
            application_graph.add_vertex(application_vertex)

            # update graph mapper
            graph_mapper.add_vertex_mapping(
                machine_vertex, vertex_slice, application_vertex)
