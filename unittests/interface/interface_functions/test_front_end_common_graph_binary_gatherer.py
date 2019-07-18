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

import unittest
from pacman.model.graphs.machine import MachineVertex, MachineGraph
from pacman.model.resources import ResourceContainer
from pacman.model.placements import Placements, Placement
from spinn_front_end_common.interface.interface_functions import (
    GraphBinaryGatherer, LocateExecutableStartType)
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary


class _TestVertexWithBinary(MachineVertex, AbstractHasAssociatedBinary):

    def __init__(self, binary_file_name, binary_start_type):
        super(_TestVertexWithBinary, self).__init__()
        self._binary_file_name = binary_file_name
        self._binary_start_type = binary_start_type

    def resources_required(self):
        return ResourceContainer()

    def get_binary_file_name(self):
        return self._binary_file_name

    def get_binary_start_type(self):
        return self._binary_start_type


class _TestVertexWithoutBinary(MachineVertex):
    def resources_required(self):
        return ResourceContainer()


class _TestExecutableFinder(object):
    def get_executable_path(self, executable_name):
        return executable_name


class TestFrontEndCommonGraphBinaryGatherer(unittest.TestCase):

    def test_call(self):
        """ Test calling the binary gatherer normally
        """

        vertex_1 = _TestVertexWithBinary(
            "test.aplx", ExecutableType.RUNNING)
        vertex_2 = _TestVertexWithBinary(
            "test2.aplx", ExecutableType.RUNNING)
        vertex_3 = _TestVertexWithBinary(
            "test2.aplx", ExecutableType.RUNNING)
        vertex_4 = _TestVertexWithoutBinary()

        graph = MachineGraph("Test")
        graph.add_vertices([vertex_1, vertex_2, vertex_3])

        placements = Placements(placements=[
            Placement(vertex_1, 0, 0, 0),
            Placement(vertex_2, 0, 0, 1),
            Placement(vertex_3, 0, 0, 2),
            Placement(vertex_4, 0, 0, 3)])

        gatherer = GraphBinaryGatherer()
        targets = gatherer.__call__(
            placements, graph, _TestExecutableFinder())
        gatherer = LocateExecutableStartType()
        start_type = gatherer.__call__(graph, placements)
        self.assertEqual(next(iter(start_type)), ExecutableType.RUNNING)
        self.assertEqual(targets.total_processors, 3)

        test_cores = targets.get_cores_for_binary("test.aplx")
        test_2_cores = targets.get_cores_for_binary("test2.aplx")
        self.assertEqual(len(test_cores), 1)
        self.assertEqual(len(test_2_cores), 2)
        self.assertIn((0, 0, 0), test_cores)
        self.assertIn((0, 0, 1), test_2_cores)
        self.assertIn((0, 0, 2), test_2_cores)

    def test_mixed_binaries(self):
        """ Test calling the binary gatherer with mixed executable types
        """

        vertex_1 = _TestVertexWithBinary(
            "test.aplx", ExecutableType.RUNNING)
        vertex_2 = _TestVertexWithBinary(
            "test2.aplx", ExecutableType.SYNC)

        placements = Placements(placements=[
            Placement(vertex_1, 0, 0, 0),
            Placement(vertex_2, 0, 0, 1)])

        graph = MachineGraph("Test")
        graph.add_vertices([vertex_1, vertex_2])

        gatherer = LocateExecutableStartType()
        results = gatherer.__call__(graph, placements=placements)
        self.assertIn(ExecutableType.RUNNING, results)
        self.assertIn(ExecutableType.SYNC, results)
        self.assertNotIn(ExecutableType.USES_SIMULATION_INTERFACE, results)
        self.assertNotIn(ExecutableType.NO_APPLICATION, results)


if __name__ == '__main__':
    unittest.main()
