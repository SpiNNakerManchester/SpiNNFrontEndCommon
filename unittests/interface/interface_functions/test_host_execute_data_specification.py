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

import tempfile
import unittest
from spinn_machine.virtual_machine import virtual_machine
from pacman.model.placements import Placement
from data_specification.constants import (
    MAX_MEM_REGIONS, APP_PTR_TABLE_BYTE_SIZE)
from data_specification.data_specification_generator import (
    DataSpecificationGenerator)
from spinn_front_end_common.interface.interface_functions import (
    HostExecuteDataSpecification)
from spinn_front_end_common.utilities.utility_objs import (
    ExecutableTargets, ExecutableType)
from spinn_front_end_common.interface.ds import DataSpecificationTargets
from spinn_front_end_common.utilities.constants import BYTES_PER_WORD


class _MockCPUInfo(object):
    """ Pretend CPU Info object
    """

    def __init__(self, user_0):
        self._user_0 = user_0

    @property
    def user(self):
        return [self._user_0]


class _MockTransceiver(object):
    """ Pretend transceiver
    """
    # pylint: disable=unused-argument

    def __init__(self, user_0_addresses):
        """

        :param user_0_addresses: dict of (x, y, p) to user_0_address
        """
        self._regions_written = list()
        self._user_0_addresses = user_0_addresses
        self._next_address = 0

    @property
    def regions_written(self):
        """ A list of tuples of (base_address, data) which has been written
        """
        return self._regions_written

    def malloc_sdram(self, x, y, size, app_id):
        address = self._next_address
        self._next_address += size
        return address

    def get_user_0_register_address_from_core(self, p):
        return self._user_0_addresses[p]

    def get_cpu_information_from_core(self, x, y, p):
        return _MockCPUInfo(self._user_0_addresses[(x, y, p)])

    def write_memory(
            self, x, y, base_address, data, n_bytes=None, offset=0,
            cpu=0, is_filename=False):
        self._regions_written.append((base_address, data))


class TestHostExecuteDataSpecification(unittest.TestCase):

    def test_call(self):
        executor = HostExecuteDataSpecification()
        transceiver = _MockTransceiver(user_0_addresses={0: 1000})
        machine = virtual_machine(2, 2)
        tempdir = tempfile.mkdtemp()

        dsg_targets = DataSpecificationTargets(machine, tempdir)
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
        targets.place_binary("text.aplx", Placement(None, 0, 0, 0),
                             ExecutableType.USES_SIMULATION_INTERFACE)
        infos = executor.execute_application_data_specs(
            transceiver, machine, 30, dsg_targets, False, targets,
            report_folder=tempdir, region_sizes=region_sizes)

        # Test regions - although 3 are created, only 2 should be uploaded
        # (0 and 2), and only the data written should be uploaded
        # The space between regions should be as allocated regardless of
        # how much data is written
        header_and_table_size = (MAX_MEM_REGIONS + 2) * BYTES_PER_WORD
        regions = transceiver.regions_written
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
