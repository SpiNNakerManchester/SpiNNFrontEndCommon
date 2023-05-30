# Copyright (c) 2023 The University of Manchester
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

from sqlite3 import IntegrityError
import unittest
from spinn_utilities.overrides import overrides
from spinn_machine.virtual_machine import virtual_machine
from spinnman.model.enums import ExecutableType
from pacman.model.graphs.machine import SimpleMachineVertex
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.ds import \
    DataSpecificationGenerator, DataSpecificationReloader, DsSqlliteDatabase
from spinn_front_end_common.utilities.exceptions import DsDatabaseException


class _TestVertexWithBinary(SimpleMachineVertex, AbstractHasAssociatedBinary):

    def __init__(self, binary_file_name, binary_start_type):
        super().__init__(0)
        self._binary_file_name = binary_file_name
        self._binary_start_type = binary_start_type

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return self._binary_file_name

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return self._binary_start_type


class TestDataSpecification(unittest.TestCase):

    def setUp(self):
        unittest_setup()

    def test_init(self):
        db = DsSqlliteDatabase()
        vertex1 = _TestVertexWithBinary(
            "off_board__system", ExecutableType.SYSTEM)
        DataSpecificationGenerator(0, 1, 2, vertex1, db)
        DataSpecificationReloader(0, 1, 2, db)

    def test_none_ds_vertex(self):
        db = DsSqlliteDatabase()
        vertex = SimpleMachineVertex(0)
        with self.assertRaises(AttributeError):
            DataSpecificationGenerator(0, 1, 2, vertex, db)

    def test_bad_x_y_ds_vertex(self):
        db = DsSqlliteDatabase()
        vertex = _TestVertexWithBinary(
            "off_board__system", ExecutableType.SYSTEM)
        with self.assertRaises(KeyError):
            DataSpecificationGenerator(3, 1, 2, vertex, db)

    def test_repeat_x_y_ds_vertex(self):
        db = DsSqlliteDatabase()
        vertex1 = _TestVertexWithBinary(
            "off_board__system", ExecutableType.SYSTEM)
        vertex2 = _TestVertexWithBinary(
            "off_board__system", ExecutableType.SYSTEM)
        DataSpecificationGenerator(0, 1, 2, vertex1, db)
        with self.assertRaises(IntegrityError):
            DataSpecificationGenerator(0, 1, 2, vertex2, db)

    def test_no_x_y_on_reload(self):
        db = DsSqlliteDatabase()
        with self.assertRaises(DsDatabaseException):
            DataSpecificationReloader(0, 1, 2, db)

    def test_core_infos(self):
        FecDataWriter.mock().set_machine(virtual_machine(16, 16))
        db = DsSqlliteDatabase()
        s1 = _TestVertexWithBinary("S1", ExecutableType.SYSTEM)
        DataSpecificationGenerator(0, 0, 2, s1, db)
        s2 = _TestVertexWithBinary("S2", ExecutableType.SYSTEM)
        DataSpecificationGenerator(5, 9, 2, s2, db)
        s3 = _TestVertexWithBinary("S3", ExecutableType.SYSTEM)
        DataSpecificationGenerator(9, 5, 2, s3, db)
        a1 = _TestVertexWithBinary(
            "A1", ExecutableType.USES_SIMULATION_INTERFACE)
        DataSpecificationGenerator(0, 0, 3, a1, db)
        a2 = _TestVertexWithBinary(
            "A2", ExecutableType.USES_SIMULATION_INTERFACE)
        DataSpecificationGenerator(0, 0, 4, a2, db)
        sys_infos = [(1, 0, 0, 2, 0, 0), (2, 5, 9, 2, 4, 8),
                     (3, 9, 5, 2, 8, 4)]
        self.assertEqual(sys_infos, db.get_core_infos(True))
        app_infos = [(4, 0, 0, 3, 0, 0), (5, 0, 0, 4, 0, 0)]
        self.assertEqual(app_infos, db.get_core_infos(False))



if __name__ == "__main__":
    unittest.main()
