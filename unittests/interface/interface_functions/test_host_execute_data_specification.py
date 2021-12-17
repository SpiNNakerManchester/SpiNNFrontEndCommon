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

import struct
import unittest
from spinn_utilities.config_holder import set_config
from spinn_utilities.overrides import overrides
from spinn_machine.virtual_machine import virtual_machine
from spinnman.transceiver import Transceiver
from spinnman.model import ExecutableTargets
from data_specification.constants import (
    MAX_MEM_REGIONS, APP_PTR_TABLE_BYTE_SIZE)
from data_specification.data_specification_generator import (
    DataSpecificationGenerator)
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.interface_functions import (
    execute_application_data_specs)
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.utilities.utility_objs import (ExecutableType)
from spinn_front_end_common.interface.ds import DataSpecificationTargets
from spinn_front_end_common.utilities.constants import BYTES_PER_WORD


class _MockTransceiver(Transceiver):
    """ Pretend transceiver
    """
    # pylint: disable=unused-argument

    def __init__(self, user_0_addresses):
        """

        :param user_0_addresses: dict of (x, y, p) to user_0_address
        """
        self._regions_written = list()
        self._next_address = 0
        self._user_0_addresses = user_0_addresses

    @property
    def regions_written(self):
        """ A list of tuples of (base_address, data) which has been written
        """
        return self._regions_written

    @overrides(Transceiver.malloc_sdram)
    def malloc_sdram(self,  x, y, size, app_id, tag=None):
        address = self._next_address
        self._next_address += size
        return address

    def get_user_0_register_address_from_core(self, p):
        return self._user_0_addresses[p]

    @overrides(Transceiver.write_memory)
    def write_memory(
            self, x, y, base_address, data, n_bytes=None, offset=0,
            cpu=0, is_filename=False):
        if isinstance(data, int):
            data = struct.pack("<I", data)
        self._regions_written.append((base_address, data))

    @overrides(Transceiver.close)
    def close(self, close_original_connections=True, power_off_machine=False):
        pass


class TestHostExecuteDataSpecification(unittest.TestCase):

    def setUp(cls):
        unittest_setup()
        set_config("Machine", "enable_advanced_monitor_support", "False")

    def test_call(self):
        transceiver = _MockTransceiver(user_0_addresses={0: 1000})
        FecDataWriter().set_transceiver(transceiver)

        dsg_targets = DataSpecificationTargets()
        with dsg_targets.create_data_spec(0, 0, 0) as spec_writer:
            spec = DataSpecificationGenerator(spec_writer)
            spec.reserve_memory_region(0, 100)
            spec.reserve_memory_region(1, 100, empty=True)
            spec.reserve_memory_region(2, 100)
            spec.switch_write_focus(0)
            spec.write_value(0)
            spec.write_value(1)
            spec.write_value(2)
            spec.switch_write_focus(2)
            spec.write_value(3)
            spec.end_specification()

        region_sizes = dict()
        region_sizes[0, 0, 0] = (
                APP_PTR_TABLE_BYTE_SIZE + sum(spec.region_sizes))

        # Execute the spec
        targets = ExecutableTargets()
        targets.add_processor(
            "text.aplx", 0, 0, 0, ExecutableType.USES_SIMULATION_INTERFACE)
        infos = execute_application_data_specs(dsg_targets, targets,
            region_sizes=region_sizes)

        # Test regions - although 3 are created, only 2 should be uploaded
        # (0 and 2), and only the data written should be uploaded
        # The space between regions should be as allocated regardless of
        # how much data is written
        header_and_table_size = (MAX_MEM_REGIONS + 2) * BYTES_PER_WORD
        regions = transceiver._regions_written
        self.assertEqual(len(regions), 4)

        # Base address for header and table
        self.assertEqual(regions[1][0], 0)

        # Base address for region 0 (after header and table)
        self.assertEqual(regions[2][0], header_and_table_size)

        # Base address for region 2
        self.assertEqual(regions[3][0], header_and_table_size + 200)

        # User 0 write address
        self.assertEqual(regions[0][0], 1000)

        # Size of header and table
        self.assertEqual(len(regions[1][1]), header_and_table_size)

        # Size of region 0
        self.assertEqual(len(regions[2][1]), 12)

        # Size of region 2
        self.assertEqual(len(regions[3][1]), 4)

        # Size of user 0
        self.assertEqual(len(regions[0][1]), 4)

        info = infos[(0, 0, 0)]
        self.assertEqual(info.memory_used, 436)
        self.assertEqual(info.memory_written, 152)

    def test_multi_spec_with_references(self):
        transceiver = _MockTransceiver(
            user_0_addresses={0: 1000, 1: 2000, 2: 3000})
        FecDataWriter().set_transceiver(transceiver)
        #machine = virtual_machine(2, 2)
        region_sizes = dict()

        dsg_targets = DataSpecificationTargets()

        with dsg_targets.create_data_spec(0, 0, 0) as spec_writer:
            spec = DataSpecificationGenerator(spec_writer)
            spec.reference_memory_region(0, 1)
            spec.end_specification()
            region_sizes[0, 0, 0] = (
                APP_PTR_TABLE_BYTE_SIZE + sum(spec.region_sizes))

        with dsg_targets.create_data_spec(0, 0, 1) as spec_writer:
            spec = DataSpecificationGenerator(spec_writer)
            spec.reserve_memory_region(0, 12, reference=1)
            spec.switch_write_focus(0)
            spec.write_value(0)
            spec.end_specification()
            region_sizes[0, 0, 1] = (
                APP_PTR_TABLE_BYTE_SIZE + sum(spec.region_sizes))

        with dsg_targets.create_data_spec(0, 0, 2) as spec_writer:
            spec = DataSpecificationGenerator(spec_writer)
            spec.reference_memory_region(0, 1)
            spec.end_specification()
            region_sizes[0, 0, 2] = (
                APP_PTR_TABLE_BYTE_SIZE + sum(spec.region_sizes))

        targets = ExecutableTargets()
        targets.add_processor(
            "text.aplx", 0, 0, 0, ExecutableType.USES_SIMULATION_INTERFACE)
        targets.add_processor(
            "text.aplx", 0, 0, 1, ExecutableType.USES_SIMULATION_INTERFACE)
        targets.add_processor(
            "text.aplx", 0, 0, 2, ExecutableType.USES_SIMULATION_INTERFACE)
        infos = execute_application_data_specs(
            dsg_targets, targets, region_sizes=region_sizes)

        # User 0 for each spec (3) + header and table for each spec (3)
        # + 1 actual region (as rest are references)
        regions = transceiver.regions_written
        self.assertEqual(len(regions), 7)

        header_and_table_size = (MAX_MEM_REGIONS + 2) * BYTES_PER_WORD
        self.assertEqual(infos[0, 0, 0].memory_used, header_and_table_size)
        self.assertEqual(infos[0, 0, 0].memory_written, header_and_table_size)
        self.assertEqual(infos[0, 0, 1].memory_used,
                         header_and_table_size + 12)
        self.assertEqual(infos[0, 0, 1].memory_written,
                         header_and_table_size + 4)
        self.assertEqual(infos[0, 0, 2].memory_used, header_and_table_size)
        self.assertEqual(infos[0, 0, 2].memory_written, header_and_table_size)

        # Find the base addresses
        base_addresses = dict()
        for base_addr, data in regions:
            if base_addr != 0 and base_addr % 1000 == 0:
                base_addresses[(base_addr // 1000) - 1] = struct.unpack(
                    "<I", data)[0]

        # Find the headers
        header_data = dict()
        for base_addr, data in regions:
            for core, addr in base_addresses.items():
                if base_addr == addr:
                    header_data[core] = struct.unpack("<34I", data)

        # Check the references - core 0 and 2 pointer 0 (position 2 because
        # of header) should be equal to core 1
        self.assertEqual(header_data[0][2], header_data[1][2])
        self.assertEqual(header_data[2][2], header_data[1][2])

    def test_multispec_with_reference_error(self):
        transceiver = _MockTransceiver(
            user_0_addresses={0: 1000, 1: 2000})
        FecDataWriter().set_transceiver(transceiver)
        region_sizes = dict()

        dsg_targets = DataSpecificationTargets()

        with dsg_targets.create_data_spec(0, 0, 0) as spec_writer:
            spec = DataSpecificationGenerator(spec_writer)
            spec.reference_memory_region(0, 2)
            spec.end_specification()
            region_sizes[0, 0, 0] = (
                APP_PTR_TABLE_BYTE_SIZE + sum(spec.region_sizes))

        with dsg_targets.create_data_spec(0, 0, 1) as spec_writer:
            spec = DataSpecificationGenerator(spec_writer)
            spec.reserve_memory_region(0, 12, reference=1)
            spec.switch_write_focus(0)
            spec.write_value(0)
            spec.end_specification()
            region_sizes[0, 0, 1] = (
                APP_PTR_TABLE_BYTE_SIZE + sum(spec.region_sizes))

        targets = ExecutableTargets()
        targets.add_processor(
            "text.aplx", 0, 0, 0, ExecutableType.USES_SIMULATION_INTERFACE)
        targets.add_processor(
            "text.aplx", 0, 0, 1, ExecutableType.USES_SIMULATION_INTERFACE)

        # ValueError because one of the regions can't be found
        with self.assertRaises(ValueError):
            execute_application_data_specs(
                dsg_targets, targets, region_sizes=region_sizes)

    def test_multispec_with_double_reference(self):
        transceiver = _MockTransceiver(
            user_0_addresses={0: 1000, 1: 2000})
        FecDataWriter().set_transceiver(transceiver)
        region_sizes = dict()

        dsg_targets = DataSpecificationTargets()

        with dsg_targets.create_data_spec(0, 0, 1) as spec_writer:
            spec = DataSpecificationGenerator(spec_writer)
            spec.reserve_memory_region(0, 12, reference=1)
            spec.reserve_memory_region(1, 12, reference=1)
            spec.switch_write_focus(0)
            spec.write_value(0)
            spec.end_specification()
            region_sizes[0, 0, 1] = (
                APP_PTR_TABLE_BYTE_SIZE + sum(spec.region_sizes))

        targets = ExecutableTargets()
        targets.add_processor(
            "text.aplx", 0, 0, 1, ExecutableType.USES_SIMULATION_INTERFACE)

        # ValueError because regions have same reference
        with self.assertRaises(ValueError):
            execute_application_data_specs(
                dsg_targets, targets, region_sizes=region_sizes)

    def test_multispec_with_wrong_chip_reference(self):
        transceiver = _MockTransceiver(
            user_0_addresses={0: 1000})
        FecDataWriter().set_transceiver(transceiver)
        region_sizes = dict()

        dsg_targets = DataSpecificationTargets()

        with dsg_targets.create_data_spec(0, 0, 0) as spec_writer:
            spec = DataSpecificationGenerator(spec_writer)
            spec.reserve_memory_region(0, 12, reference=1)
            spec.switch_write_focus(0)
            spec.write_value(0)
            spec.end_specification()
            region_sizes[0, 0, 0] = (
                APP_PTR_TABLE_BYTE_SIZE + sum(spec.region_sizes))

        with dsg_targets.create_data_spec(1, 1, 0) as spec_writer:
            spec = DataSpecificationGenerator(spec_writer)
            spec.reference_memory_region(0, 1)
            spec.end_specification()
            region_sizes[1, 1, 0] = (
                APP_PTR_TABLE_BYTE_SIZE + sum(spec.region_sizes))

        targets = ExecutableTargets()
        targets.add_processor(
            "text.aplx", 0, 0, 0, ExecutableType.USES_SIMULATION_INTERFACE)
        targets.add_processor(
            "text.aplx", 1, 1, 0, ExecutableType.USES_SIMULATION_INTERFACE)

        # ValueError because the reference is on a different chip
        with self.assertRaises(ValueError):
            execute_application_data_specs(
                dsg_targets, targets, region_sizes=region_sizes)

    def test_multispec_with_wrong_chip_reference_on_close(self):
        transceiver = _MockTransceiver(
            user_0_addresses={0: 1000})
        FecDataWriter().set_transceiver(transceiver)
        region_sizes = dict()

        dsg_targets = DataSpecificationTargets()

        with dsg_targets.create_data_spec(1, 1, 0) as spec_writer:
            spec = DataSpecificationGenerator(spec_writer)
            spec.reference_memory_region(0, 1)
            spec.end_specification()
            region_sizes[1, 1, 0] = (
                APP_PTR_TABLE_BYTE_SIZE + sum(spec.region_sizes))

        with dsg_targets.create_data_spec(0, 0, 0) as spec_writer:
            spec = DataSpecificationGenerator(spec_writer)
            spec.reserve_memory_region(0, 12, reference=1)
            spec.switch_write_focus(0)
            spec.write_value(0)
            spec.end_specification()
            region_sizes[0, 0, 0] = (
                APP_PTR_TABLE_BYTE_SIZE + sum(spec.region_sizes))

        targets = ExecutableTargets()
        targets.add_processor(
            "text.aplx", 0, 0, 0, ExecutableType.USES_SIMULATION_INTERFACE)
        targets.add_processor(
            "text.aplx", 1, 1, 0, ExecutableType.USES_SIMULATION_INTERFACE)

        # ValueError because the reference is on a different chip
        with self.assertRaises(ValueError):
            execute_application_data_specs(
               dsg_targets, targets, region_sizes=region_sizes)


if __name__ == "__main__":
    unittest.main()
