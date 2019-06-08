import unittest
import struct
import shutil
import numpy
from spinn_machine import SDRAM
from pacman.model.resources import ResourceContainer
from pacman.model.graphs.common import Slice, GraphMapper
from pacman.model.placements import Placements, Placement
from pacman.model.graphs.application import ApplicationVertex
from pacman.model.graphs.machine import MachineVertex
from data_specification.constants import MAX_MEM_REGIONS
from data_specification.utility_calls import get_region_base_address_offset
from spinn_front_end_common.abstract_models import (
    AbstractRewritesDataSpecification)
from spinn_front_end_common.interface.interface_functions import (
    DSGRegionReloader)


class _TestMachineVertex(MachineVertex):
    """ A simple machine vertex for testing
    """

    def resources_required(self):
        return ResourceContainer()


class _TestApplicationVertex(
        ApplicationVertex, AbstractRewritesDataSpecification):
    """ An application vertex that can rewrite data spec
    """

    def __init__(self, n_atoms, reload_region_data):
        """
        :param n_atoms: The number of atoms in the vertex
        :param reload_region_data: list of tuples of (region_id, data to write)
        """
        super(_TestApplicationVertex, self).__init__()
        self._n_atoms = n_atoms
        self._regenerate_call_count = 0
        self._requires_regions_to_be_reloaded = True
        self._reload_region_data = reload_region_data

    @property
    def n_atoms(self):
        return self._n_atoms

    @property
    def regenerate_call_count(self):
        """ Indicates the number of times regenerate_data_specification\
            has been called
        """
        return self._regenerate_call_count

    def get_resources_used_by_atoms(self, vertex_slice):
        return ResourceContainer()

    def create_machine_vertex(
            self, vertex_slice, resources_required, label=None,
            constraints=None):
        return _TestMachineVertex()

    def requires_memory_regions_to_be_reloaded(self):
        return self._requires_regions_to_be_reloaded

    def mark_regions_reloaded(self):
        self._requires_regions_to_be_reloaded = False

    def regenerate_data_specification(self, spec, placement):
        for region_id, data in self._reload_region_data:
            spec.reserve_memory_region(region_id, len(data) * 4)
            spec.switch_write_focus(region_id)
            spec.write_array(data)
        spec.end_specification()
        self._regenerate_call_count += 1


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

    def __init__(self, user_0_addresses, region_addresses):
        """

        :param user_0_addresses: dict of (x, y, p) to user_0_address
        :param region_addresses:\
            list of constants.MAX_MEM_REGIONS addresses to which the\
            base address will be added to each
        """
        self._regions_rewritten = list()
        self._user_0_addresses = user_0_addresses
        self._region_addresses = region_addresses

    @property
    def regions_rewritten(self):
        """ A list of tuples of (base_address, data) which has been written
        """
        return self._regions_rewritten

    def get_cpu_information_from_core(self, x, y, p):
        return _MockCPUInfo(self._user_0_addresses[(x, y, p)])

    def read_memory(self, x, y, base_address, length, cpu=0):
        addresses = [i + base_address for i in self._region_addresses]
        return struct.pack(
            "<{}I".format(MAX_MEM_REGIONS), *addresses)

    def write_memory(
            self, x, y, base_address, data, n_bytes=None, offset=0,
            cpu=0, is_filename=False):
        self._regions_rewritten.append((base_address, data))


class TestFrontEndCommonDSGRegionReloader(unittest.TestCase):

    def test_with_application_vertices(self):
        """ Test that an application vertex's data is rewritten correctly
        """
        # Create a default SDRAM to set the max to default
        SDRAM()
        reload_region_data = [
            (0, [0] * 10),
            (1, [1] * 20)
        ]
        vertex = _TestApplicationVertex(10, reload_region_data)
        m_slice_1 = Slice(0, 4)
        m_slice_2 = Slice(5, 9)
        m_vertex_1 = vertex.create_machine_vertex(m_slice_1, None, None, None)
        m_vertex_2 = vertex.create_machine_vertex(m_slice_2, None, None, None)

        graph_mapper = GraphMapper()
        graph_mapper.add_vertex_mapping(m_vertex_1, m_slice_1, vertex)
        graph_mapper.add_vertex_mapping(m_vertex_2, m_slice_2, vertex)

        placements = Placements([
            Placement(m_vertex_1, 0, 0, 1),
            Placement(m_vertex_2, 0, 0, 2)
        ])

        user_0_addresses = {
            (placement.x, placement.y, placement.p): i * 1000
            for i, placement in enumerate(placements.placements)
        }
        region_addresses = [i for i in range(MAX_MEM_REGIONS)]
        transceiver = _MockTransceiver(user_0_addresses, region_addresses)

        reloader = DSGRegionReloader()
        reloader.__call__(
            transceiver, placements, "localhost", "test", False, "test",
            graph_mapper)

        regions_rewritten = transceiver.regions_rewritten

        # Check that the number of times the data has been regenerated is
        # correct
        self.assertEqual(vertex.regenerate_call_count, placements.n_placements)

        # Check that the number of regions rewritten is correct
        self.assertEqual(
            len(transceiver.regions_rewritten),
            placements.n_placements * len(reload_region_data))

        # Check that the data rewritten is correct
        for i, placement in enumerate(placements.placements):
            user_0_address = user_0_addresses[
                placement.x, placement.y, placement.p]
            for j in range(len(reload_region_data)):
                pos = (i * len(reload_region_data)) + j
                region, data = reload_region_data[j]
                address = get_region_base_address_offset(
                    user_0_address, 0) + region_addresses[region]
                data = bytearray(numpy.array(data, dtype="uint32").tobytes())

                # Check that the base address and data written is correct
                self.assertEqual(regions_rewritten[pos], (address, data))

        # Delete data files
        shutil.rmtree("test")


if __name__ == "__main__":
    unittest.main()
