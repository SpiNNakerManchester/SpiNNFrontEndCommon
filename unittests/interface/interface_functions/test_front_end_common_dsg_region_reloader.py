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
import shutil
import numpy
from spinn_utilities.overrides import overrides
from spinn_machine import SDRAM
from pacman.model.placements import Placements, Placement
from data_specification.constants import MAX_MEM_REGIONS
from data_specification.utility_calls import get_region_base_address_offset
from spinn_front_end_common.abstract_models import (
    AbstractRewritesDataSpecification)
from spinn_front_end_common.interface.config_setup import reset_configs
from spinn_front_end_common.interface.interface_functions import (
    DSGRegionReloader)
from spinn_front_end_common.utilities.constants import BYTES_PER_WORD
from spinn_front_end_common.utilities.helpful_functions import n_word_struct
from pacman.model.graphs.machine import (SimpleMachineVertex)
from spinnman.transceiver import Transceiver
from spinnman.model import CPUInfo

# test specific stuff
reload_region_data = [
    (0, [0] * 10),
    (1, [1] * 20)
]
regenerate_call_count = 0


class _TestMachineVertex(
        SimpleMachineVertex, AbstractRewritesDataSpecification):
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


class _MockCPUInfo(object):
    """ Pretend CPU Info object
    """

    def __init__(self, user_0):
        self._user_0 = user_0

    @property
    @overrides(CPUInfo.user)
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
        self._regions_rewritten = list()
        self._user_0_addresses = user_0_addresses

    @overrides(Transceiver.get_cpu_information_from_core)
    def get_cpu_information_from_core(self, x, y, p):
        return _MockCPUInfo(self._user_0_addresses[(x, y, p)])

    @overrides(Transceiver.read_memory)
    def read_memory(self, x, y, base_address, length, cpu=0):
        addresses = [i + base_address for i in range(MAX_MEM_REGIONS)]
        return n_word_struct(MAX_MEM_REGIONS).pack(*addresses)

    @overrides(Transceiver.write_memory)
    def write_memory(
            self, x, y, base_address, data, n_bytes=None, offset=0,
            cpu=0, is_filename=False):
        self._regions_rewritten.append((base_address, data))


class TestFrontEndCommonDSGRegionReloader(unittest.TestCase):

    def setUp(self):
        reset_configs()

    def test_with_application_vertices(self):
        """ Test that an application vertex's data is rewritten correctly
        """
        # Create a default SDRAM to set the max to default
        SDRAM()
        m_vertex_1 = _TestMachineVertex()
        m_vertex_2 = _TestMachineVertex()

        placements = Placements([
            Placement(m_vertex_1, 0, 0, 1),
            Placement(m_vertex_2, 0, 0, 2)
        ])

        user_0_addresses = {
            placement.location: i * 1000
            for i, placement in enumerate(placements.placements)
        }
        transceiver = _MockTransceiver(user_0_addresses)

        reloader = DSGRegionReloader()
        reloader.__call__(transceiver, placements, "localhost", "test")

        regions_rewritten = transceiver._regions_rewritten

        # Check that the number of times the data has been regenerated is
        # correct
        self.assertEqual(regenerate_call_count, placements.n_placements)

        # Check that the number of regions rewritten is correct
        self.assertEqual(
            len(transceiver._regions_rewritten),
            placements.n_placements * len(reload_region_data))

        # Check that the data rewritten is correct
        for i, placement in enumerate(placements.placements):
            user_0_address = user_0_addresses[placement.location]
            for j in range(len(reload_region_data)):
                pos = (i * len(reload_region_data)) + j
                region, data = reload_region_data[j]
                address = get_region_base_address_offset(
                    user_0_address, 0) + region
                data = bytearray(numpy.array(data, dtype="uint32").tobytes())

                # Check that the base address and data written is correct
                self.assertEqual(regions_rewritten[pos], (address, data))

        # Delete data files
        shutil.rmtree("test")


if __name__ == "__main__":
    unittest.main()
