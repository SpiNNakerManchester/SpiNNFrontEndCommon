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
from spinn_front_end_common.interface.interface_functions import (
    HostExecuteDataSpecification)
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.utilities.utility_objs import (ExecutableType)
from spinn_front_end_common.interface.ds import DataSpecificationTargets
from spinn_front_end_common.utilities.constants import BYTES_PER_WORD


class _MockTransceiver(object):
    """ Pretend transceiver
    """
    # pylint: disable=unused-argument

    def __init__(self):
        """

        :param user_0_addresses: dict of (x, y, p) to user_0_address
        """
        self._regions_written = list()
        self._next_address = 0

    @overrides(Transceiver.malloc_sdram)
    def malloc_sdram(self,  x, y, size, app_id, tag=None):
        address = self._next_address
        self._next_address += size
        return address

    @staticmethod
    @overrides(Transceiver.get_user_0_register_address_from_core)
    def get_user_0_register_address_from_core(p):
        return {0: 1000}[p]

    @overrides(Transceiver.write_memory)
    def write_memory(
            self, x, y, base_address, data, n_bytes=None, offset=0,
            cpu=0, is_filename=False):
        if isinstance(data, int):
            data = struct.pack("<I", data)
        self._regions_written.append((base_address, data))


class TestHostExecuteDataSpecification(unittest.TestCase):

    def setUp(cls):
        unittest_setup()
        set_config("Machine", "enable_advanced_monitor_support", "False")

    def test_call(self):
        executor = HostExecuteDataSpecification()
        transceiver = _MockTransceiver()
        machine = virtual_machine(2, 2)

        dsg_targets = DataSpecificationTargets(machine)
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
        infos = executor.execute_application_data_specs(
            transceiver, machine, 30, dsg_targets, targets,
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
        self.assertEqual(info.memory_used, 372)
        self.assertEqual(info.memory_written, 88)


if __name__ == "__main__":
    unittest.main()
