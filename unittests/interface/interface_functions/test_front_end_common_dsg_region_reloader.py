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
from typing import BinaryIO, Optional, Sequence, Tuple, Union
from spinn_utilities.config_holder import set_config
from spinn_utilities.overrides import overrides
from spinn_machine.version.version_strings import VersionStrings
from spinnman.model.enums import ExecutableType
from pacman.model.placements import Placements, Placement
from spinn_front_end_common.abstract_models import (
    AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification,
    AbstractRewritesDataSpecification)
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.interface_functions import (
    reload_dsg_regions)
from pacman.model.graphs.machine import (SimpleMachineVertex)
from spinnman.transceiver.mockable_transceiver import MockableTransceiver
from spinnman.model import CPUInfo
from spinn_front_end_common.interface.ds import (
    DataSpecificationGenerator, DataSpecificationReloader, DsSqlliteDatabase)
from spinn_front_end_common.utilities.exceptions import DataSpecException

# test specific stuff
# vertex/ p: region, size, data
reload_region_data = {
    # core 4
    4: [
        (0, 40, [0] * 10),
        (1, 120, [1] * 20)
    ],
    # core 5
    5: [
        (5, 120, [3] * 15),
        (7, 80, [4] * 20),
        (10, 90, [5] * 4)
    ]
}

regenerate_call_count = 0


class _TestMachineVertex(
        SimpleMachineVertex, AbstractHasAssociatedBinary,
        AbstractGeneratesDataSpecification, AbstractRewritesDataSpecification):
    """ A simple machine vertex for testing
    """

    def __init__(self) -> None:
        super().__init__(None)
        self._requires_regions_to_be_reloaded = True

    @overrides(AbstractRewritesDataSpecification.reload_required)
    def reload_required(self) -> bool:
        return self._requires_regions_to_be_reloaded

    @overrides(AbstractRewritesDataSpecification.set_reload_required)
    def set_reload_required(self, new_value: bool) -> None:
        self._requires_regions_to_be_reloaded = new_value

    @overrides(AbstractRewritesDataSpecification.regenerate_data_specification)
    def regenerate_data_specification(self, spec: DataSpecificationReloader,
                                      placement: Placement) -> None:
        global regenerate_call_count
        for region_id, size, data in reload_region_data[placement.p]:
            spec.reserve_memory_region(region_id, size)
            spec.switch_write_focus(region_id)
            spec.write_array(data)
        spec.end_specification()
        regenerate_call_count += 1

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self) -> str:
        raise NotImplementedError()

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self) -> ExecutableType:
        return ExecutableType.USES_SIMULATION_INTERFACE

    @overrides(AbstractGeneratesDataSpecification.generate_data_specification)
    def generate_data_specification(self, spec: DataSpecificationGenerator,
                                    placement: Placement) -> None:
        raise NotImplementedError()


class _MockCPUInfo(object):
    """ Pretend CPU Info object
    """

    def __init__(self, user_0):
        self._user_0 = user_0

    @property
    @overrides(CPUInfo.user)
    def user(self) -> Sequence[int]:
        return [self._user_0]


class _MockTransceiver(MockableTransceiver):
    """ Pretend transceiver
    """
    # pylint: disable=unused-argument

    def __init__(self) -> None:
        self._regions_rewritten = list()

    @overrides(MockableTransceiver.write_memory)
    def write_memory(
            self, x: int, y: int, base_address: int,
            data: Union[BinaryIO, bytes, int, str], *,
            n_bytes: Optional[int] = None, offset: int = 0, cpu: int = 0,
            get_sum: bool = False) -> Tuple[int, int]:
        self._regions_rewritten.append((base_address, data))
        return (-1, -1)


class TestFrontEndCommonDSGRegionReloader(unittest.TestCase):

    def setUp(self) -> None:
        unittest_setup()
        set_config("Machine", "versions", VersionStrings.ANY.text)
        set_config("Reports", "write_text_specs", "True")

    def test_with_good_sizes(self) -> None:
        """ Test that an application vertex's data is rewritten correctly
        """
        writer = FecDataWriter.mock()

        m_vertex_1 = _TestMachineVertex()
        m_vertex_2 = _TestMachineVertex()
        placements = Placements([
            Placement(m_vertex_1, 0, 0, 4),
            Placement(m_vertex_2, 0, 0, 5)
        ])
        writer.set_placements(placements)

        transceiver = _MockTransceiver()
        writer.set_transceiver(transceiver)
        with DsSqlliteDatabase() as ds:
            for placement in placements:
                ds.set_core(
                    placement.x, placement.y, placement.p, placement.vertex)
                base = placement.p * 1000
                regions = reload_region_data[placement.p]
                for (reg_num, size, _) in regions:
                    ds.set_memory_region(
                        placement.x, placement.y, placement.p, reg_num, size,
                        None, None)
                    ds.set_region_pointer(
                        placement.x, placement.y, placement.p, reg_num, base)
                    base += size

        reload_dsg_regions()

        regions_rewritten = transceiver._regions_rewritten

        # Check that the number of times the data has been regenerated is
        # correct
        self.assertEqual(regenerate_call_count, placements.n_placements)

        # Check that the number of regions rewritten is correct
        self.assertEqual(
            len(regions_rewritten),
            sum(len(x) for x in reload_region_data.values()))

        # Check that the data rewritten is correct
        pos = 0
        for placement in placements:
            regions = reload_region_data[placement.p]
            address = placement.p * 1000
            for (_, size, data) in regions:
                data = bytearray(numpy.array(data, dtype="uint32").tobytes())
                # Check that the base address and data written is correct
                self.assertEqual(regions_rewritten[pos], (address, data))
                pos += 1
                address += size

    def test_with_size_changed(self) -> None:
        """ Test that an application vertex's data is rewritten correctly
        """
        writer = FecDataWriter.mock()

        m_vertex_1 = _TestMachineVertex()
        m_vertex_2 = _TestMachineVertex()
        placements = Placements([
            Placement(m_vertex_1, 0, 0, 4),
            Placement(m_vertex_2, 0, 0, 5)
        ])
        writer.set_placements(placements)

        transceiver = _MockTransceiver()
        writer.set_transceiver(transceiver)
        with DsSqlliteDatabase() as ds:
            for placement in placements:
                ds.set_core(
                    placement.x, placement.y, placement.p, placement.vertex)
                base = placement.p * 1000
                regions = reload_region_data[placement.p]
                for (reg_num, size, _) in regions:
                    ds.set_memory_region(
                        placement.x, placement.y, placement.p, reg_num, size-1,
                        None, None)
                    ds.set_region_pointer(
                        placement.x, placement.y, placement.p, reg_num, base)
                    base += size

        with self.assertRaises(DataSpecException):
            reload_dsg_regions()


if __name__ == "__main__":
    unittest.main()
