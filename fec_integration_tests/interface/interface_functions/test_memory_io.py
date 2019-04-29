import struct
import tempfile
import numpy
from pacman.executor import PACMANAlgorithmExecutor
from pacman.model.resources import ResourceContainer
from pacman.model.graphs.machine import MachineVertex, MachineGraph
from pacman.model.placements import Placements, Placement
from spinnman.model import HeapElement
from spinnman.exceptions import SpinnmanInvalidParameterException
from spinnman.messages.spinnaker_boot import SystemVariableDefinition
from spinn_front_end_common.utilities.function_list import (
    get_front_end_common_pacman_xml_paths)
from spinn_front_end_common.abstract_models.abstract_uses_memory_io import (
    AbstractUsesMemoryIO)


class _MockTransceiver(object):
    # pylint: disable=unused-argument

    _HEAP_SIZE = 120 * 1024 * 1024

    def __init__(self):
        self._data = dict()
        self._heap = dict()

    def _get_memory(self, x, y):
        if (x, y) not in self._data:
            self._data[(x, y)] = numpy.zeros(self._HEAP_SIZE, dtype="uint8")
        return self._data[(x, y)]

    def _get_heap(self, x, y, heap):
        if (x, y, heap) not in self._heap:
            self._heap[x, y, heap] = [
                HeapElement(0, self._HEAP_SIZE, 0x00000000)]
        return self._heap[x, y, heap]

    def write_memory(self, x, y, address, data, n_bytes=None,
                     offset=0, cpu=0, is_filename=False):  # @UnusedVariable
        memory = self._get_memory(x, y)
        if isinstance(data, int):
            memory[address:address + 4] = numpy.array(
                [data], dtype="uint32").view(dtype="uint8")
        else:
            if n_bytes is None:
                n_bytes = len(data)
            numpy_data = numpy.frombuffer(data[:n_bytes], dtype="uint8")
            memory[address:address + n_bytes] = numpy_data

    def read_memory(self, x, y, address, n_bytes, cpu=0):
        memory = self._get_memory(x, y)
        return bytearray(memory[address:address + n_bytes])

    def fill_memory(
            self, x, y, address, repeat_value, bytes_to_fill, data_type):
        memory = self._get_memory(x, y)
        data_to_fill = numpy.array([repeat_value], dtype="uint{}".format(
            data_type.value * 8)).view("uint8")
        data_to_write = numpy.tile(
            data_to_fill, bytes_to_fill // data_type.value)
        memory[address:address + bytes_to_fill] = data_to_write

    def get_heap(self, x, y, heap):
        return self._get_heap(x, y, heap)

    def malloc_sdram(self, x, y, size, app_id, tag):
        space_required = size + 8
        heap = self._get_heap(
            x, y, SystemVariableDefinition.sdram_heap_address)
        space = None
        index = None
        for i, element in enumerate(heap):
            if element.is_free and element.size >= space_required:
                space = element
                index = i
                break
        if space is None:
            raise SpinnmanInvalidParameterException(
                "SDRAM Allocation response base address", 0,
                "Could not allocate {} bytes of SDRAM".format(size))
        free = 0xFFFF0000 | (app_id << 8) | tag
        next_space = None
        if index + 1 < len(heap):
            next_space = heap[index + 1]
        else:
            next_space = HeapElement(
                space.next_address, space.next_address, 0xFFFFFFFF)
        heap.pop(index)
        if space.size > space_required:
            new_space = HeapElement(
                space.block_address + space_required,
                space.next_address, 0x00000000)
            next_space = new_space
            heap.insert(index, new_space)
        heap.insert(index, HeapElement(
            space.block_address, next_space.block_address, free))
        return space.block_address


class MyVertex(MachineVertex, AbstractUsesMemoryIO):

    def __init__(self):
        super(MyVertex, self).__init__()
        self._test_tag = None
        self._tag = None

    @property
    def resources_required(self):
        return ResourceContainer()

    def get_memory_io_data_size(self):
        return 100

    def write_data_to_memory_io(self, memory, tag):
        memory.write(struct.pack("<I", tag))
        memory.seek(0)
        self._tag = tag
        self._test_tag, = struct.unpack("<I", memory.read(4))


def test_memory_io():
    vertex = MyVertex()
    graph = MachineGraph("Test")
    graph.add_vertex(vertex)
    placements = Placements()
    placements.add_placement(Placement(vertex, 0, 0, 1))
    transceiver = _MockTransceiver()
    temp = tempfile.mkdtemp()
    print("ApplicationDataFolder = {}".format(temp))
    inputs = {
        "MemoryTransceiver": transceiver,
        "MemoryMachineGraph": graph,
        "MemoryPlacements": placements,
        "IPAddress": "testing",
        "ApplicationDataFolder": temp,
        "APPID": 30
    }
    algorithms = ["WriteMemoryIOData"]
    executor = PACMANAlgorithmExecutor(
        algorithms, [], inputs, [], [], [],
        xml_paths=get_front_end_common_pacman_xml_paths())
    executor.execute_mapping()
    assert(vertex._test_tag == vertex._tag)
