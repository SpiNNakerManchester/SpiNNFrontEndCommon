import struct
from pacman.model.resources.resource_container import ResourceContainer
from spinnman.transceiver import create_transceiver_from_hostname
from pacman.executor.pacman_algorithm_executor import PACMANAlgorithmExecutor
import tempfile
from pacman.model.graphs.machine.machine_vertex import MachineVertex
from pacman.model.graphs.machine.machine_graph import MachineGraph
from spinn_front_end_common.utilities.function_list \
    import get_front_end_common_pacman_xml_paths
from spinn_front_end_common.abstract_models.abstract_uses_memory_io \
    import AbstractUsesMemoryIO


class MyVertex(MachineVertex, AbstractUsesMemoryIO):

    def __init__(self):
        MachineVertex.__init__(self)
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
        self._test_tag = struct.unpack("<I", memory.read(4))[0]


def test_memory_io():
    hostname = "spinn-10.cs.man.ac.uk"
    vertex = MyVertex()
    graph = MachineGraph("Test")
    graph.add_vertex(vertex)
    transceiver = create_transceiver_from_hostname(hostname, 2)
    transceiver.ensure_board_is_ready()
    machine = transceiver.get_machine_details()
    temp = tempfile.mkdtemp()
    print "ApplicationDataFolder =", temp
    inputs = {
        "MemoryTransceiver": transceiver,
        "MemoryMachineGraph": graph,
        "MemoryExtendedMachine": machine,
        "IPAddress": hostname,
        "ApplicationDataFolder": temp,
        "APPID": 30
    }
    algorithms = ["OneToOnePlacer", "WriteMemoryIOData"]
    executor = PACMANAlgorithmExecutor(
        algorithms, [], inputs, [],
        xml_paths=get_front_end_common_pacman_xml_paths())
    executor.execute_mapping()
    transceiver.stop_application(30)
    transceiver.close()
    assert(vertex._test_tag == vertex._tag)
