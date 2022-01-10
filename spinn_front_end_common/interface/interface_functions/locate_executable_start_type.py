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
from spinn_machine import CoreSubsets
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.utility_objs import ExecutableType


def locate_executable_start_type():
    """
    Discovers where applications of particular types need to be launched.

    :param ~pacman.model.graphs.machine.MachineGraph graph:
    :rtype: dict(ExecutableType,~spinn_machine.CoreSubsets or None)
    """
    view = FecDataView()
    graph = FecDataView.get_runtime_machine_graph()
    if not graph.vertices:
        return {ExecutableType.NO_APPLICATION: None}

    binary_start_types = dict()

    progress = ProgressBar(
        graph.n_vertices, "Finding executable start types")
    for vertex in progress.over(graph.vertices):
        # try to locate binary type, but possible it doesn't have one
        if isinstance(vertex, AbstractHasAssociatedBinary):
            bin_type = vertex.get_binary_start_type()
            # update core subset with location of the vertex on the machine
            if bin_type not in binary_start_types:
                binary_start_types[bin_type] = CoreSubsets()

            __add_vertex_to_subset(vertex, binary_start_types[bin_type])

    # only got apps with no binary, such as external devices.
    # return no app
    if not binary_start_types:
        return {ExecutableType.NO_APPLICATION: None}

    return binary_start_types


def __add_vertex_to_subset(machine_vertex, core_subsets):
    """
    :param ~.MachineVertex machine_vertex:
    :param ~.CoreSubsets core_subsets:
    """
    placement = FecDataView.get_placement_of_vertex(machine_vertex)
    core_subsets.add_processor(
        x=placement.x, y=placement.y, processor_id=placement.p)
