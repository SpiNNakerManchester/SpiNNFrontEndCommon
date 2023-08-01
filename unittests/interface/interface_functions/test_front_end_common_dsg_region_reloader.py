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
import numpy
from spinn_utilities.overrides import overrides
from pacman.model.placements import Placements, Placement
from spinn_front_end_common.abstract_models import (
    AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification,
    AbstractRewritesDataSpecification)
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.interface_functions import (
    reload_dsg_regions)
from spinn_front_end_common.utilities.constants import (
    BYTES_PER_WORD, MAX_MEM_REGIONS, TABLE_TYPE)
from spinn_front_end_common.utilities.helpful_functions import (
    get_region_base_address_offset, n_word_struct)
from pacman.model.graphs.machine import (SimpleMachineVertex)
from spinnman.transceiver.transceiver import Transceiver
from spinnman.model import CPUInfo

# test specific stuff
reload_region_data = [
    (0, [0] * 10),
    (1, [1] * 20)
]
regenerate_call_count = 0


class _TestMachineVertex(
        SimpleMachineVertex, AbstractHasAssociatedBinary,
        AbstractGeneratesDataSpecification, AbstractRewritesDataSpecification):
    """ A simple machine vertex for testing
    """

    def __init__(self):
        super().__init__(None)
        self._requires_regions_to_be_reloaded = True

    @overrides(AbstractRewritesDataSpecification.reload_required)
    def reload_required(self):
        return self._requires_regions_to_be_reloaded

    @overrides(AbstractRewritesDataSpecification.set_reload_required)
    def set_reload_required(self, new_value):
        self._requires_regions_to_be_reloaded = new_value

    @overrides(AbstractRewritesDataSpecification.regenerate_data_specification)
    def regenerate_data_specification(self, spec, placement):
        global regenerate_call_count
        for region_id, data in reload_region_data:
            spec.reserve_memory_region(region_id, len(data) * BYTES_PER_WORD)
            spec.switch_write_focus(region_id)
            spec.write_array(data)
        spec.end_specification()
        regenerate_call_count += 1

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        raise NotImplementedError()

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        raise NotImplementedError()

    @overrides(AbstractGeneratesDataSpecification.generate_data_specification)
    def generate_data_specification(self, spec, placement):
        raise NotImplementedError()


class _MockCPUInfo(object):
    """ Pretend CPU Info object
    """

    def __init__(self, user_0):
        self._user_0 = user_0

    @property
    @overrides(CPUInfo.user)
    def user(self):
        return [self._user_0]


class _MockTransceiver(Transceiver):
    """ Pretend transceiver
    """
    # pylint: disable=unused-argument

    def __init__(self, user_0_addresses):
        """
        :param user_0_addresses: dict of (x, y, p) to user_0_address
        """
        self._regions_rewritten = list()
        self._user_0_addresses = user_0_addresses

    @overrides(Transceiver.get_cpu_information_from_core)
    def get_cpu_information_from_core(self, x, y, p):
        return _MockCPUInfo(self._user_0_addresses[(x, y, p)])

    @overrides(Transceiver.read_memory)
    def read_memory(self, x, y, base_address, length, cpu=0):
        ptr_table_end = get_region_base_address_offset(
            base_address, MAX_MEM_REGIONS)
        addresses = [((i * 512) + ptr_table_end, 0, 0)
                     for i in range(MAX_MEM_REGIONS)]
        addresses = [j for lst in addresses for j in lst]
        return n_word_struct(MAX_MEM_REGIONS * 3).pack(*addresses)

    @overrides(Transceiver.write_memory)
    def write_memory(
            self, x, y, base_address, data, n_bytes=None, offset=0,
            cpu=0, is_filename=False, get_sum=False):
        self._regions_rewritten.append((base_address, data))

    @overrides(Transceiver.close)
    def close(self):
        pass


class TestFrontEndCommonDSGRegionReloader(unittest.TestCase):

    def setUp(self):
        unittest_setup()

    def test_with_application_vertices(self):
        """ Test that an application vertex's data is rewritten correctly
        """
        raise self.skipTest("pointer now from database")
        writer = FecDataWriter.mock()
        m_vertex_1 = _TestMachineVertex()
        m_vertex_2 = _TestMachineVertex()

        placements = Placements([
            Placement(m_vertex_1, 0, 0, 1),
            Placement(m_vertex_2, 0, 0, 2)
        ])

        user_0_addresses = {
            placement.location: i * MAX_MEM_REGIONS * 512
            for i, placement in enumerate(placements.placements)
        }
        transceiver = _MockTransceiver(user_0_addresses)
        writer.set_transceiver(transceiver)
        writer.set_placements(placements)
        writer.set_ipaddress("localhost")

        reload_dsg_regions()

        regions_rewritten = transceiver._regions_rewritten

        # Check that the number of times the data has been regenerated is
        # correct
        self.assertEqual(regenerate_call_count, placements.n_placements)

        # Check that the number of regions rewritten is correct
        # (time 2 as there are 2 writes per region)
        self.assertEqual(
            len(regions_rewritten),
            placements.n_placements * len(reload_region_data) * 2)

        # Check that the data rewritten is correct
        for i, placement in enumerate(placements.placements):
            user_0_address = user_0_addresses[placement.location]
            ptr_table_addr = get_region_base_address_offset(user_0_address, 0)
            ptr_table = numpy.frombuffer(transceiver.read_memory(
                placement.x, placement.y, ptr_table_addr, 0),
                dtype=TABLE_TYPE)
            for j in range(len(reload_region_data)):
                pos = ((i * len(reload_region_data)) + j) * 2
                region, data = reload_region_data[j]
                address = ptr_table[region]["pointer"]
                data = bytearray(numpy.array(data, dtype="uint32").tobytes())

                # Check that the base address and data written is correct
                self.assertEqual(regions_rewritten[pos], (address, data))


if __name__ == "__main__":
    unittest.main()
