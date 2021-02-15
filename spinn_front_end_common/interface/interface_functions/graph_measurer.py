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
from pacman.utilities.utility_objs import ResourceTracker
from pacman.utilities.algorithm_utilities.placer_algorithm_utilities import (
    sort_vertices_by_known_constraints)


class GraphMeasurer(object):
    """ Works out how many chips a machine graph needs.
    """

    __slots__ = []

    def __call__(self, machine_graph, machine, plan_n_timesteps):
        """
        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
            The machine_graph to measure.
        :param ~spinn_machine.Machine machine:
            The machine with respect to which to partition the application
            graph.
        :param int plan_n_timesteps: Number of timesteps to plan for.
        :return: The size of the graph in number of chips.
        :rtype: int
        """

        # check that the algorithm can handle the constraints
        ResourceTracker.check_constraints(machine_graph.vertices)

        ordered_vertices = sort_vertices_by_known_constraints(
            machine_graph.vertices)

        # Iterate over vertices and allocate
        progress = ProgressBar(machine_graph.n_vertices, "Measuring the graph")

        resource_tracker = ResourceTracker(machine, plan_n_timesteps)
        for vertex in progress.over(ordered_vertices):
            resource_tracker.allocate_constrained_resources(
                vertex.resources_required, vertex.constraints)
        return len(resource_tracker.keys)
