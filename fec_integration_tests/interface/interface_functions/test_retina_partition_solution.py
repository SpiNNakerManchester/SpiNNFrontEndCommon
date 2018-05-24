from pacman.model.graphs.machine import MachineGraph
from pacman.model.graphs.machine import MachineEdge
from pacman.model.graphs.machine import MachineVertex
from pacman.model.graphs.impl import OutgoingEdgePartition
from pacman.model.routing_info import BaseKeyAndMask
from pacman.executor.injection_decorator import injection_context
from pacman.model.constraints.key_allocator_constraints\
    .fixed_key_and_mask_constraint import FixedKeyAndMaskConstraint
from spinn_front_end_common.abstract_models import \
    AbstractProvidesIncomingPartitionConstraints
import unittest
from spinn_front_end_common.utility_models \
    .reverse_ip_tag_multicast_source_machine_vertex import \
    ReverseIPTagMulticastSourceMachineVertex
from spinn_front_end_common.interface.interface_functions\
    .process_partition_constraints import ProcessPartitionConstraints
from spinn_front_end_common.utilities.exceptions import ConfigurationException

RETINA_SIZE_X = 128
RETINA_SIZE_Y = 128
RETINA_KEY = 1 << 16
RETINA_SIZE_IN_BITS = 7
RETINA_FILTER_MASK = 0xFFFFFF80


class DestinationVertex(
        MachineVertex, AbstractProvidesIncomingPartitionConstraints):

    def __init__(
            self, row_id, retina_base_key, retina_y_size_in_bits,
            retina_filter_mask, label):
        MachineVertex.__init__(self, label, [])
        AbstractProvidesIncomingPartitionConstraints.__init__(self)
        self._row_id = row_id
        self._retina_base_key = retina_base_key
        self._retina_y_size_in_bits = retina_y_size_in_bits
        self._retina_filter_mask = retina_filter_mask

    def get_incoming_partition_constraints(self, partition):
        base_key = self._retina_base_key | \
            (self._row_id << self._retina_y_size_in_bits)
        return [FixedKeyAndMaskConstraint(
            keys_and_masks=[BaseKeyAndMask(
                base_key=base_key, mask=self._retina_filter_mask)])]

    @property
    def resources_required(self):
        resources = ResourceContainer(
            cpu_cycles=CPUCyclesPerTickResource(),
            dtcm=DTCMResource(), sdram=SDRAMResource())
        return resources


class TestRetinaPartitionSolution(unittest.TestCase):

    def test_fully_covered_retina(self):
        machine_graph = MachineGraph(label="test_graph")
        spike_train = [[]] * ((RETINA_SIZE_X * RETINA_SIZE_Y) - 1)
        fake_retina = ReverseIPTagMulticastSourceMachineVertex(
            virtual_key=RETINA_KEY,
            buffer_notification_ip_address="0.0.0.0",
            n_keys=(RETINA_SIZE_X * RETINA_SIZE_Y) - 1,
            label="Input Vertex", send_buffer_times=spike_train)
        machine_graph.add_vertex(fake_retina)

        filters = list()
        for filter in range(0, RETINA_SIZE_X):
            vertex = DestinationVertex(
                retina_base_key=RETINA_KEY, row_id=filter,
                retina_y_size_in_bits=RETINA_SIZE_IN_BITS,
                retina_filter_mask=RETINA_FILTER_MASK,
                label="filter_vertex_{}".format(filter))
            machine_graph.add_vertex(vertex)
            filters.append(vertex)

        name_id = 0
        for filter in filters:
            machine_graph.add_edge(
                MachineEdge(fake_retina, filter), "filter_{}".format(name_id))
            name_id += 1

        with injection_context({'MemoryMachineGraph': machine_graph}):
            partition_checker = ProcessPartitionConstraints()
            partition_checker(machine_graph)

    def test_not_fully_covered_retina(self):
        machine_graph = MachineGraph(label="test_graph")
        spike_train = [[]] * ((RETINA_SIZE_X * RETINA_SIZE_Y) - 1)
        fake_retina = ReverseIPTagMulticastSourceMachineVertex(
            virtual_key=RETINA_KEY,
            buffer_notification_ip_address="0.0.0.0",
            n_keys=(RETINA_SIZE_X * RETINA_SIZE_Y) - 1,
            label="Input Vertex", send_buffer_times=spike_train)
        machine_graph.add_vertex(fake_retina)

        filters = list()
        for filter in range(0, RETINA_SIZE_X - 1):
            vertex = DestinationVertex(
                retina_base_key=RETINA_KEY, row_id=filter,
                retina_y_size_in_bits=RETINA_SIZE_IN_BITS,
                retina_filter_mask=RETINA_FILTER_MASK,
                label="filter_vertex_{}".format(filter))
            machine_graph.add_vertex(vertex)
            filters.append(vertex)

        name_id = 0
        for filter in filters:
            machine_graph.add_edge(
                MachineEdge(fake_retina, filter), "filter_{}".format(name_id))
            name_id += 1

        with injection_context({'MemoryMachineGraph': machine_graph}):
            partition_checker = ProcessPartitionConstraints()
            with self.assertRaises(ConfigurationException):
                partition_checker(machine_graph)

    def test_retina_with_bigger_n_keys_than_needed(self):
        pass

if __name__ == "__main__":
    unittest.main()
