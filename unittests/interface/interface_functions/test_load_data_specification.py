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

from sqlite3 import IntegrityError
import struct
import unittest
from spinn_utilities.config_holder import set_config
from spinn_utilities.overrides import overrides
from spinnman.transceiver.version5transceiver import Version5Transceiver
from spinnman.model.enums import ExecutableType
from pacman.model.graphs.machine import SimpleMachineVertex
from pacman.model.placements import Placements
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.ds import (
    DataSpecificationGenerator)
from spinn_front_end_common.interface.interface_functions import (
    load_application_data_specs)
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.ds import DsSqlliteDatabase
from spinn_front_end_common.utilities.constants import (
    BYTES_PER_WORD, MAX_MEM_REGIONS)
from spinn_front_end_common.utilities.exceptions import DataSpecException


class _MockTransceiver(Version5Transceiver):
    """ Pretend transceiver
    """
    # pylint: disable=unused-argument

    def __init__(self):
        self._regions_written = list()
        self._next_address = 0

    @property
    def regions_written(self):
        """ A list of tuples of (base_address, data) which has been written
        """
        return self._regions_written

    @overrides(Version5Transceiver.malloc_sdram)
    def malloc_sdram(self,  x, y, size, app_id, tag=None):
        address = self._next_address
        self._next_address += size
        return address

    @overrides(Version5Transceiver.write_memory)
    def write_memory(
            self, x, y, base_address, data, *,
            n_bytes=None, offset=0, cpu=0, get_sum=False):
        if isinstance(data, int):
            data = struct.pack("<I", data)
        self._regions_written.append((base_address, data))

    @overrides(Version5Transceiver.close)
    def close(self):
        pass


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


class TestLoadDataSpecification(unittest.TestCase):

    def setUp(self):
        unittest_setup()
        set_config("Machine", "enable_advanced_monitor_support", "False")
        set_config("Machine", "version", 5)

    def test_call(self):
        writer = FecDataWriter.mock()
        transceiver = _MockTransceiver()
        writer.set_transceiver(transceiver)

        vertex = _TestVertexWithBinary(
            "binary", ExecutableType.USES_SIMULATION_INTERFACE)
        with DsSqlliteDatabase() as db:
            spec = DataSpecificationGenerator(0, 0, 0, vertex, db)
            spec.reserve_memory_region(0, 100)
            spec.reserve_memory_region(1, 100)
            spec.reserve_memory_region(2, 100)
            spec.switch_write_focus(0)
            spec.write_value(0)
            spec.write_value(1)
            spec.write_value(2)
            spec.switch_write_focus(2)
            spec.write_value(3)
            spec.end_specification()

        load_application_data_specs()

        # Test regions - although 3 are created, only 2 should be uploaded
        # (0 and 2), and only the data written should be uploaded
        # The space between regions should be as allocated regardless of
        # how much data is written
        header_and_table_size = ((MAX_MEM_REGIONS * 3) + 2) * BYTES_PER_WORD
        regions = transceiver.regions_written
        self.assertEqual(len(regions), 4)

        # Base address for header and table
        self.assertEqual(regions[3][0], 0)

        # Base address for region 0 (after header and table)
        self.assertEqual(regions[1][0], header_and_table_size)

        # Base address for region 2
        self.assertEqual(regions[2][0], header_and_table_size + 200)

        # User 0 write address
        self.assertEqual(regions[0][0], 3842011248)

        # Size of header and table
        self.assertEqual(len(regions[3][1]), header_and_table_size)

        # Size of region 0
        self.assertEqual(len(regions[1][1]), 12)

        # Size of region 2
        self.assertEqual(len(regions[2][1]), 4)

        # Size of user 0
        self.assertEqual(len(regions[0][1]), 4)

        with DsSqlliteDatabase() as db:
            pc = list(db.get_info_for_cores())
            _, _, memory_used, memory_written = pc[0]
            # We reserved 3 regions at 100 each
            self.assertEqual(memory_used, header_and_table_size + 300)
            self.assertEqual(header_and_table_size + 300,
                             db.get_memory_to_malloc(0, 0, 0))
            # We wrote 4 words
            self.assertEqual(memory_written, header_and_table_size + 16)
            self.assertEqual(db.get_memory_to_write(0, 0, 0),
                             header_and_table_size + 16)

    def test_multi_spec_with_references(self):
        writer = FecDataWriter.mock()
        transceiver = _MockTransceiver()
        writer.set_transceiver(transceiver)

        vertex = _TestVertexWithBinary(
            "binary", ExecutableType.USES_SIMULATION_INTERFACE)

        with DsSqlliteDatabase() as db:
            spec = DataSpecificationGenerator(0, 0, 0, vertex, db)
            spec.reference_memory_region(0, 1)
            spec.end_specification()

            spec = DataSpecificationGenerator(0, 0, 1, vertex, db)
            spec.reserve_memory_region(0, 12, reference=1)
            spec.switch_write_focus(0)
            spec.write_value(0)
            spec.end_specification()

            spec = DataSpecificationGenerator(0, 0, 2, vertex, db)
            spec.reference_memory_region(0, 1)
            spec.end_specification()

        load_application_data_specs()

        # User 0 for each spec (3) + header and table for each spec (3)
        # + 1 actual region (as rest are references)
        regions = transceiver.regions_written
        self.assertEqual(len(regions), 7)

        header_and_table_size = ((MAX_MEM_REGIONS * 3) + 2) * BYTES_PER_WORD

        with DsSqlliteDatabase() as db:
            self.assertEqual(header_and_table_size,
                             db.get_memory_to_malloc(0, 0, 0))
            self.assertEqual(header_and_table_size,
                             db.get_memory_to_write(0, 0, 0))

            self.assertEqual(header_and_table_size + 12,
                             db.get_memory_to_malloc(0, 0, 1))
            self.assertEqual(header_and_table_size + 4,
                             db.get_memory_to_write(0, 0, 1))

            self.assertEqual(header_and_table_size,
                             db.get_memory_to_malloc(0, 0, 2))
            self.assertEqual(header_and_table_size,
                             db.get_memory_to_write(0, 0, 2))

        # Find the base addresses
        base_addresses = dict()
        for base_addr, data in regions:
            # user 0 p 0
            if base_addr == 3842011248:
                base_addresses[0] = struct.unpack("<I", data)[0]
            # user 0 p 1
            if base_addr == 3842011376:
                base_addresses[1] = struct.unpack("<I", data)[0]
            # user 0 p 2
            if base_addr == 3842011504:
                base_addresses[2] = struct.unpack("<I", data)[0]

        # Find the headers
        header_data = dict()
        for base_addr, data in regions:
            for core, addr in base_addresses.items():
                if base_addr == addr:
                    header_data[core] = struct.unpack("<98I", data)

        # Check the references - core 0 and 2 pointer 0 (position 2 because
        # of header) should be equal to core 1
        self.assertEqual(header_data[0][2 * 3], header_data[1][2 * 3])
        self.assertEqual(header_data[2][2 * 3], header_data[1][2 * 3])

    def test_multispec_with_reference_error(self):
        writer = FecDataWriter.mock()
        transceiver = _MockTransceiver()
        writer.set_transceiver(transceiver)
        vertex = _TestVertexWithBinary(
            "binary", ExecutableType.USES_SIMULATION_INTERFACE)

        with DsSqlliteDatabase() as db:
            spec = DataSpecificationGenerator(0, 0, 0, vertex, db)
            spec.reference_memory_region(0, 2)
            spec.end_specification()

            spec = DataSpecificationGenerator(0, 0, 1, vertex, db)
            spec.reserve_memory_region(0, 12, reference=1)
            spec.switch_write_focus(0)
            spec.write_value(0)
            spec.end_specification()

        with DsSqlliteDatabase() as db:
            bad = list(db.get_unlinked_references())
            # x, y, p, region, ref, ref_label
            self.assertEqual([(0, 0, 0, 0, 2, "")], bad)

        # DataSpecException because one of the regions can't be found
        with self.assertRaises(DataSpecException):
            load_application_data_specs()

    def test_multispec_with_double_reference(self):
        writer = FecDataWriter.mock()
        transceiver = _MockTransceiver()
        writer.set_transceiver(transceiver)
        vertex = _TestVertexWithBinary(
            "binary", ExecutableType.USES_SIMULATION_INTERFACE)

        with DsSqlliteDatabase() as db:
            spec = DataSpecificationGenerator(0, 0, 1, vertex, db)
            spec.reserve_memory_region(0, 12, reference=1)
            with self.assertRaises(IntegrityError):
                spec.reserve_memory_region(1, 12, reference=1)

    def test_multispec_with_wrong_chip_reference(self):
        writer = FecDataWriter.mock()
        transceiver = _MockTransceiver()
        writer.set_transceiver(transceiver)
        writer.set_placements(Placements([]))
        vertex = _TestVertexWithBinary(
            "binary", ExecutableType.USES_SIMULATION_INTERFACE)

        with DsSqlliteDatabase() as db:

            spec = DataSpecificationGenerator(0, 0, 0, vertex, db)
            spec.reserve_memory_region(0, 12, reference=1)
            spec.switch_write_focus(0)
            spec.write_value(0)
            spec.end_specification()

            spec = DataSpecificationGenerator(1, 1, 0, vertex, db)
            spec.reference_memory_region(0, 1)
            spec.end_specification()

            # This safety query should yield nothing
            bad = list(db.get_unlinked_references())
            # x, y, p, region, ref, ref_label
            self.assertEqual([(1, 1, 0, 0, 1, "")], bad)

        with DsSqlliteDatabase() as db:
            # DataSpecException because the reference is on a different chip
            with self.assertRaises(DataSpecException):
                load_application_data_specs()


if __name__ == "__main__":
    unittest.main()
