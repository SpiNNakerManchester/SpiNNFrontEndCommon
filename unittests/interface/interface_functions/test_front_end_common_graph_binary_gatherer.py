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

import unittest
from spinn_utilities.executable_finder import ExecutableFinder
from spinn_utilities.overrides import overrides
from spinnman.model.enums import ExecutableType
from pacman.model.graphs.machine import SimpleMachineVertex
from pacman.model.graphs.application.abstract import (
    AbstractOneAppOneMachineVertex)
from pacman.model.placements import Placements, Placement
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.interface_functions import (
    graph_binary_gatherer, locate_executable_start_type)
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary


class _TestAppVertexWithBinary(AbstractOneAppOneMachineVertex):

    def __init__(self, binary_file_name, binary_start_type):
        AbstractOneAppOneMachineVertex.__init__(
            self, _TestVertexWithBinary(binary_file_name, binary_start_type),
            label=None)


class _TestVertexWithBinary(SimpleMachineVertex, AbstractHasAssociatedBinary):

    def __init__(self, binary_file_name, binary_start_type):
        super().__init__(None)
        self._binary_file_name = binary_file_name
        self._binary_start_type = binary_start_type

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self) -> str:
        return self._binary_file_name

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self) -> ExecutableType:
        return self._binary_start_type


class _TestSimpleAppVertex(AbstractOneAppOneMachineVertex):

    def __init__(self) -> None:
        AbstractOneAppOneMachineVertex.__init__(
            self, SimpleMachineVertex(None), label=None)


class _TestExecutableFinder(object):

    @overrides(ExecutableFinder.get_executable_path)
    def get_executable_path(self, executable_name: str) -> str:
        return executable_name


class TestFrontEndCommonGraphBinaryGatherer(unittest.TestCase):

    def setUp(self) -> None:
        unittest_setup()

    def test_call(self) -> None:
        """ Test calling the binary gatherer normally
        """

        vertex_1 = _TestAppVertexWithBinary(
            "test.aplx", ExecutableType.RUNNING)

        vertex_2 = _TestAppVertexWithBinary(
            "test2.aplx", ExecutableType.RUNNING)
        vertex_3 = _TestAppVertexWithBinary(
            "test2.aplx", ExecutableType.RUNNING)

        placements = Placements(placements=[
            Placement(vertex_1.machine_vertex, 0, 0, 0),
            Placement(vertex_2.machine_vertex, 0, 0, 1),
            Placement(vertex_3.machine_vertex, 0, 0, 2)])

        writer = FecDataWriter.mock()
        writer.set_placements(placements)
        writer._set_executable_finder(_TestExecutableFinder())
        targets = graph_binary_gatherer()
        start_type = locate_executable_start_type()
        self.assertEqual(next(iter(start_type)), ExecutableType.RUNNING)
        self.assertEqual(targets.total_processors, 3)

        test_cores = targets.get_cores_for_binary("test.aplx")
        test_2_cores = targets.get_cores_for_binary("test2.aplx")
        self.assertEqual(len(test_cores), 1)
        self.assertEqual(len(test_2_cores), 2)
        self.assertIn((0, 0, 0), test_cores)
        self.assertIn((0, 0, 1), test_2_cores)
        self.assertIn((0, 0, 2), test_2_cores)

        writer._set_executable_finder(ExecutableFinder())

    def test_mixed_binaries(self) -> None:
        """ Test calling the binary gatherer with mixed executable types
        """

        vertex_1 = _TestAppVertexWithBinary(
            "test.aplx", ExecutableType.RUNNING)
        vertex_2 = _TestAppVertexWithBinary(
            "test2.aplx", ExecutableType.SYNC)

        placements = Placements(placements=[
            Placement(vertex_1.machine_vertex, 0, 0, 0),
            Placement(vertex_2.machine_vertex, 0, 0, 1)])

        writer = FecDataWriter.mock()
        writer.set_placements(placements)
        results = locate_executable_start_type()
        self.assertIn(ExecutableType.RUNNING, results)
        self.assertIn(ExecutableType.SYNC, results)
        self.assertNotIn(ExecutableType.USES_SIMULATION_INTERFACE, results)
        self.assertNotIn(ExecutableType.NO_APPLICATION, results)


if __name__ == '__main__':
    unittest.main()
