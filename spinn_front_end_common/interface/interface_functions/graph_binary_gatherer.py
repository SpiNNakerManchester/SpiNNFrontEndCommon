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

import logging
from spinnman.model import ExecutableTargets
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from pacman.model.graphs import AbstractVirtual
from spinn_front_end_common.utilities.exceptions import (
    ExecutableNotFoundException)
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary

logger = FormatAdapter(logging.getLogger(__name__))


class GraphBinaryGatherer(object):
    """ Extracts binaries to be executed.
    """

    __slots__ = ["_exe_finder", "_exe_targets"]

    def __init__(self):
        self._exe_finder = None
        self._exe_targets = None

    def __call__(self, placements, graph, executable_finder):
        """
        :param ~pacman.model.placements.Placements placements:
        :param ~pacman.model.graphs.machine.MachineGraph graph:
        :param executable_finder:
        :type executable_finder:
            ~spinn_utilities.executable_finder.ExecutableFinder
        :rtype: ExecutableTargets
        """
        self._exe_finder = executable_finder
        self._exe_targets = ExecutableTargets()
        progress = ProgressBar(graph.n_vertices, "Finding binaries")
        for vertex in progress.over(graph.vertices):
            placement = placements.get_placement_of_vertex(vertex)
            self.__get_binary(placement, vertex)

        return self._exe_targets

    def __get_binary(self, placement, vertex):
        """
        :param ~.Placement placement:
        :param ~.AbstractVertex vertex:
        """
        # if the vertex cannot be executed, ignore it
        if not isinstance(vertex, AbstractHasAssociatedBinary):
            if not isinstance(vertex, AbstractVirtual):
                msg = (
                    "Vertex {} does not implement either "
                    "AbstractHasAssociatedBinary or AbstractVirtual. So it is "
                    "unclear if it should or should not have a binary")
                logger.error(msg.format(vertex), vertex)
            return

        # Get name of binary from vertex
        binary_name = vertex.get_binary_file_name()
        exec_type = vertex.get_binary_start_type()

        # Attempt to find this within search paths
        binary_path = self._exe_finder.get_executable_path(binary_name)
        if binary_path is None:
            raise ExecutableNotFoundException(binary_name)

        self._exe_targets.add_processor(
            binary_path, placement.x, placement.y, placement.p, exec_type)
