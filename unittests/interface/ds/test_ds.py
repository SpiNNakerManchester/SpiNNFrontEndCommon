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
from spinn_machine import Chip
from spinn_machine.virtual_machine import virtual_machine
from spinnman.model.enums import ExecutableType
from pacman.model.graphs.machine import SimpleMachineVertex
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinn_front_end_common.data.fec_data_writer import (
    FecDataView, FecDataWriter)
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.ds import \
    DataSpecificationGenerator, DataSpecificationReloader, DsSqlliteDatabase
from spinn_front_end_common.utilities.constants import (
    APP_PTR_TABLE_BYTE_SIZE)
from spinn_front_end_common.utilities.exceptions import (
    DataSpecException, DsDatabaseException)


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
            DataSpecificationGenerator(10, 10, 2, vertex, db)

    def test_repeat_x_y_ds_vertex(self):
        db = DsSqlliteDatabase()
        vertex1 = _TestVertexWithBinary(
            "v1", ExecutableType.SYSTEM)
        vertex2 = _TestVertexWithBinary(
            "v2", ExecutableType.SYSTEM)
        DataSpecificationGenerator(0, 1, 2, vertex1, db)
        with self.assertRaises(IntegrityError):
            DataSpecificationGenerator(0, 1, 2, vertex2, db)

    def test_core_infos(self):
        FecDataWriter.mock().set_machine(virtual_machine(16, 16))
        db = DsSqlliteDatabase()
        self.assertEqual([], db.get_core_infos(True))
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
        sys_infos = [(0, 0, 2, 0, 0), (5, 9, 2, 4, 8),
                     (9, 5, 2, 8, 4)]
        self.assertEqual(sys_infos, db.get_core_infos(True))
        app_infos = [(0, 0, 3, 0, 0), (0, 0, 4, 0, 0)]
        self.assertEqual(app_infos, db.get_core_infos(False))

    def test_bad_ethernet(self):
        bad = Chip(10, 10, 15, None, 100, 8, 8)
        FecDataView.get_machine().add_chip(bad)
        db = DsSqlliteDatabase()
        vertex = _TestVertexWithBinary(
            "bad", ExecutableType.SYSTEM)
        with self.assertRaises(IntegrityError):
            DataSpecificationGenerator(10, 10, 2, vertex, db)

    def test_reserve_memory_region(self):
        db = DsSqlliteDatabase()
        vertex = _TestVertexWithBinary(
            "binary", ExecutableType.SYSTEM)
        dsg = DataSpecificationGenerator(0, 1, 2, vertex, db)
        dsg.reserve_memory_region(10, 123456, "test_region")
        size = db.get_region_size(0, 1, 2, 10)
        self.assertEqual(123456, size)
        # May not repeat a location
        with self.assertRaises(IntegrityError):
            dsg.reserve_memory_region(10, 24, "repeat_region")

        # check reloading
        dsr = DataSpecificationReloader(0, 1, 2, db)
        # ok to repeat serve as long as the size is the same
        dsr.reserve_memory_region(10, 123456, "different_name")
        # But the wrong size foes BOOM!
        with self.assertRaises(DataSpecException):
            dsr.reserve_memory_region(10, 12345, "different_name")
        with self.assertRaises(DataSpecException):
            dsr.reserve_memory_region(10, 212345, "different_name")

        # test round up
        dsg.reserve_memory_region(12, 1234, "test_region")
        # the 1234 is rounded up to next 4
        size = db.get_region_size(0, 1, 2, 12)
        self.assertEqual(1236, size)

        # dict will have all regions set for this core
        sizes = db.get_region_sizes(0, 1, 2)
        self.assertEqual(2, len(sizes))
        self.assertEqual(sizes[10], 123456)
        self.assertEqual(sizes[12], 1236)

        # total sizes
        self.assertEqual(123456 + 1236, db.get_total_regions_size(0, 1, 2))

        # If core unknown dict empty and size 0
        self.assertEqual({}, db.get_region_sizes(0, 1, 3))
        self.assertEqual(0, db.get_total_regions_size(0, 1, 3))

    def test_switch_write_focus(self):
        db = DsSqlliteDatabase()
        vertex = _TestVertexWithBinary(
            "binary", ExecutableType.SYSTEM)
        dsg = DataSpecificationGenerator(0, 1, 2, vertex, db)
        dsg.reserve_memory_region(10, 123456, "test_region")
        dsg.switch_write_focus(10)
        # check internal fields used later are correct
        self.assertEqual(123456, dsg._size)
        # Error is switching into a region not reserved
        with self.assertRaises(DsDatabaseException):
            dsg.switch_write_focus(8)

    def test_pointers(self):
        db = DsSqlliteDatabase()

        # You can use a reference before defining it
        vertex1 = _TestVertexWithBinary(
            "binary1", ExecutableType.SYSTEM)
        dsg1 = DataSpecificationGenerator(1, 1, 1, vertex1, db)
        dsg1.reference_memory_region(6, 2)

        vertex2 = _TestVertexWithBinary(
            "binary2", ExecutableType.SYSTEM)
        dsg2 = DataSpecificationGenerator(1, 1, 2, vertex2, db)
        dsg2.reserve_memory_region(2, 100)
        dsg2.reserve_memory_region(6, 200, reference=1)
        dsg2.reserve_memory_region(4, 400, reference=2)

        # You can use a reference after defining it
        vertex3 = _TestVertexWithBinary(
            "binary1", ExecutableType.SYSTEM)
        dsg3 = DataSpecificationGenerator(1, 1, 3, vertex3, db)
        dsg3.reference_memory_region(11, 1)
        # And also use a reference more than once
        dsg3.reference_memory_region(9, 2)

        # You can use a reference before defining it
        # So you can reference a bad region
        vertex4 = _TestVertexWithBinary(
            "binary4", ExecutableType.SYSTEM)
        dsg4 = DataSpecificationGenerator(1, 1, 4, vertex4, db)
        dsg4.reference_memory_region(8, 3, "oops")

        # Will be none before set_base_address called
        self.assertEqual(None, db.get_region_pointer(1, 1, 2, 6))

        self.assertIsNone(db.get_start_address(1, 1, 2))
        size = db.set_start_address(1, 1, 2, 1000)
        self.assertEqual(APP_PTR_TABLE_BYTE_SIZE + 100 + 200 + 400, size)
        base_adr = db.get_start_address(1, 1, 2)
        self.assertEqual(1000, base_adr)
        p_info = list(db.get_region_pointers_and_content(1, 1, 2))
        p2 = 1000 + APP_PTR_TABLE_BYTE_SIZE
        p4 = p2 + 100
        p6 = p4 + 400
        self.assertEqual([(2, p2, None), (4, p4, None), (6, p6, None)], p_info)
        self.assertEqual(p2, db.get_region_pointer(1, 1, 2, 2))
        self.assertEqual(p4, db.get_region_pointer(1, 1, 2, 4))
        self.assertEqual(p6, db.get_region_pointer(1, 1, 2, 6))

        # call fails with unknown region
        with self.assertRaises(DsDatabaseException):
            db.get_region_pointer(1, 1, 2, 7)

        info = list(db.get_reference_pointers(1, 1, 1))
        self.assertEqual([(6, p4)], info)

        info = list(db.get_reference_pointers(1, 1, 2))
        self.assertEqual([], info)

        info = list(db.get_reference_pointers(1, 1, 3))
        self.assertIn((9, p4), info)
        self.assertIn((11, p6), info)

        # GIGO referrence 3 never reserved
        info = list(db.get_reference_pointers(1, 1, 4))
        self.assertEqual([(8, None)], info)

        bad = list(db.get_unlinked_references())
        self.assertEqual([(1, 1, 4, 8, 3, "oops")], bad)

        info = list(db.get_reference_pointers(1, 4, 4))
        self.assertEqual([], info)

        # will fails on an unknown region
        with self.assertRaises(DsDatabaseException):
            db.get_region_pointer(1, 1, 2, 10)

        # will fails on an unknown core
        with self.assertRaises(DsDatabaseException):
            db.set_start_address(1, 1, 8, 1000)
        with self.assertRaises(DsDatabaseException):
            db.get_start_address(1, 1, 8)

    def test_write(self):
        db = DsSqlliteDatabase()
        vertex = _TestVertexWithBinary(
            "binary", ExecutableType.SYSTEM)

        # Emtpy if no cores set
        self.assertEqual([], list(db.get_info_for_cores()))

        # You can use a reference before defining it
        dsg = DataSpecificationGenerator(0, 1, 2, vertex, db)
        dsg.reserve_memory_region(5, 100, "unused")
        dsg.reserve_memory_region(10, 123456, "test_region")
        dsg.switch_write_focus(10)
        dsg.write_value(12)
        dsg.write_array([34, 56])
        dsg.end_specification()

        dsg = DataSpecificationGenerator(0, 1, 3, vertex, db)
        dsg.reserve_memory_region(7, 444, "unused")

        self.assertEqual(123456, db.get_region_size(0, 1, 2, 10))

        pcs = list(db.get_region_pointers_and_content(0, 1, 2))
        self.assertEqual(2, len(pcs))

        region, pointer, content = pcs[0]
        self.assertEqual(5, region)
        self.assertIsNone(pointer)
        self.assertIsNone(content)

        region, pointer, content = pcs[1]
        self.assertEqual(10, region)
        self.assertIsNone(pointer)
        self.assertEqual(3 * 4, len(content))
        self.assertEqual(
            bytearray(b'\x0c\x00\x00\x00"\x00\x00\x008\x00\x00\x00'), content)

        pcs = list(db.get_region_pointers_and_content(0, 1, 6))
        self.assertEqual(0, len(pcs))

        info = list(db.get_info_for_cores())
        size2 = APP_PTR_TABLE_BYTE_SIZE + 100 + 123456
        size3 = APP_PTR_TABLE_BYTE_SIZE + 444
        self.assertIn(((0, 1, 2), None, size2, 404), info)
        self.assertIn(((0, 1, 3), None, size3, APP_PTR_TABLE_BYTE_SIZE), info)

        with self.assertRaises(DsDatabaseException):
            db.set_region_content(
                0, 1, 4, 5, bytearray(b'\x0c\x00\x00\x00'), "test")

    def test_ds_cores(self):
        db = DsSqlliteDatabase()
        vertex = _TestVertexWithBinary(
            "binary", ExecutableType.SYSTEM)
        self.assertEqual([], list(db.get_ds_cores()))
        self.assertEqual(0, db.get_n_ds_cores())

        DataSpecificationGenerator(0, 1, 3, vertex, db)
        DataSpecificationGenerator(0, 1, 4, vertex, db)
        DataSpecificationGenerator(0, 2, 3, vertex, db)
        self.assertEqual(3, db.get_n_ds_cores())
        cores = list(db.get_ds_cores())
        self.assertEqual(3, len(cores))
        self.assertIn((0, 1, 3), cores)
        self.assertIn((0, 1, 4), cores)
        self.assertIn((0, 2, 3), cores)

    def test_memory_to_write(self):
        db = DsSqlliteDatabase()
        vertex = _TestVertexWithBinary(
            "binary", ExecutableType.SYSTEM)
        dsg = DataSpecificationGenerator(0, 1, 3, vertex, db)
        dsg.reserve_memory_region(5, 200, "used")
        dsg.switch_write_focus(5)
        dsg.write_array([34, 56])

        dsg = DataSpecificationGenerator(0, 1, 4, vertex, db)
        dsg = DataSpecificationGenerator(0, 1, 5, vertex, db)
        dsg.reserve_memory_region(5, 100, "unused")
        self.assertEqual(APP_PTR_TABLE_BYTE_SIZE,
                         db.get_memory_to_write(0, 1, 4))
        self.assertEqual(APP_PTR_TABLE_BYTE_SIZE,
                         db.get_memory_to_write(0, 1, 3))


if __name__ == "__main__":
    unittest.main()
