import unittest
from pacman.model.graphs.machine import (
    MachineGraph, MachineEdge, MachineVertex)
from pacman.model.resources import (
    ConstantSDRAM, CPUCyclesPerTickResource, DTCMResource, ResourceContainer)
from pacman.model.routing_info import BaseKeyAndMask
from pacman.executor.injection_decorator import injection_context
from pacman.model.constraints.key_allocator_constraints import (
    FixedKeyAndMaskConstraint)
from spinn_front_end_common.abstract_models import (
    AbstractProvidesIncomingPartitionConstraints)
from spinn_front_end_common.utility_models import (
    ReverseIPTagMulticastSourceMachineVertex)
from spinn_front_end_common.interface.interface_functions\
    .process_partition_constraints import (
        ProcessPartitionConstraints)
from spinn_front_end_common.utilities.exceptions import ConfigurationException

RETINA_SIZE_X = 128
RETINA_SIZE_Y = 128
RETINA_KEY = 1 << 16
RETINA_SIZE_IN_BITS = 7
RETINA_FILTER_MASK = 0xFFFFFF80


class FakeRetinaVertex(
        MachineVertex, AbstractProvidesIncomingPartitionConstraints):
    def __init__(
            self, row_id, retina_base_key, retina_y_size_in_bits,
            retina_filter_mask, label):
        MachineVertex.__init__(self, label, [])
        self._row_id = row_id
        self._retina_base_key = retina_base_key
        self._retina_y_size_in_bits = retina_y_size_in_bits
        self._retina_filter_mask = retina_filter_mask

    def get_incoming_partition_constraints(self, partition):
        base_key = self._retina_base_key | (
            self._row_id << self._retina_y_size_in_bits)
        return [FixedKeyAndMaskConstraint(
            keys_and_masks=[BaseKeyAndMask(
                base_key=base_key, mask=self._retina_filter_mask)])]

    @property
    def resources_required(self):
        resources = ResourceContainer(
            cpu_cycles=CPUCyclesPerTickResource(1),
            dtcm=DTCMResource(1), sdram=ConstantSDRAM(1))
        return resources


class TestRetinaPartitionSolution(unittest.TestCase):

    def test_fully_covered_retina(self):
        machine_graph = MachineGraph(label="test_graph")
        spike_train = [[]] * ((RETINA_SIZE_X * RETINA_SIZE_Y) - 1)
        fake_retina = ReverseIPTagMulticastSourceMachineVertex(
            virtual_key=RETINA_KEY,
            n_keys=(RETINA_SIZE_X * RETINA_SIZE_Y) - 1,
            label="Input Vertex", send_buffer_times=spike_train)
        machine_graph.add_vertex(fake_retina)

        filters = list()
        for _filter in range(0, RETINA_SIZE_X):
            vertex = FakeRetinaVertex(
                retina_base_key=RETINA_KEY, row_id=_filter,
                retina_y_size_in_bits=RETINA_SIZE_IN_BITS,
                retina_filter_mask=RETINA_FILTER_MASK,
                label="filter_vertex_{}".format(_filter))
            machine_graph.add_vertex(vertex)
            filters.append(vertex)

        name_id = 0
        for _filter in filters:
            machine_graph.add_edge(
                MachineEdge(fake_retina, _filter), "filter_{}".format(name_id))
            name_id += 1

        with injection_context({'MemoryMachineGraph': machine_graph}):
            partition_checker = ProcessPartitionConstraints()
            partition_checker(machine_graph)

    def test_not_fully_covered_retina(self):
        machine_graph = MachineGraph(label="test_graph")
        spike_train = [[]] * ((RETINA_SIZE_X * RETINA_SIZE_Y) - 1)
        fake_retina = ReverseIPTagMulticastSourceMachineVertex(
            virtual_key=RETINA_KEY,
            n_keys=(RETINA_SIZE_X * RETINA_SIZE_Y) - 1,
            label="Input Vertex", send_buffer_times=spike_train)
        machine_graph.add_vertex(fake_retina)

        filters = list()
        for _filter in range(0, RETINA_SIZE_X - 1):
            vertex = FakeRetinaVertex(
                retina_base_key=RETINA_KEY, row_id=_filter,
                retina_y_size_in_bits=RETINA_SIZE_IN_BITS,
                retina_filter_mask=RETINA_FILTER_MASK,
                label="filter_vertex_{}".format(_filter))
            machine_graph.add_vertex(vertex)
            filters.append(vertex)

        name_id = 0
        for _filter in filters:
            machine_graph.add_edge(
                MachineEdge(fake_retina, _filter), "filter_{}".format(name_id))
            name_id += 1

        with injection_context({'MemoryMachineGraph': machine_graph}):
            partition_checker = ProcessPartitionConstraints()
            with self.assertRaises(ConfigurationException):
                partition_checker(machine_graph)


if __name__ == "__main__":
    unittest.main()
