from pacman.model.graphs.machine.impl.machine_vertex import MachineVertex
import struct
import unittest
from pacman.model.graphs.machine.impl.machine_graph import MachineGraph
from pacman.model.resources.resource_container import ResourceContainer
from spinnman.transceiver import create_transceiver_from_hostname
from pacman.executor.pacman_algorithm_executor import PACMANAlgorithmExecutor
import tempfile
from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.abstract_models.abstract_uses_memory_io \
    import AbstractUsesMemoryIO


class MyVertex(unittest.TestCase, MachineVertex, AbstractUsesMemoryIO):

    def __init__(self, methodName="runTest"):
        unittest.TestCase.__init__(self, methodName)
        MachineVertex.__init__(self, ResourceContainer(), label="MyVertex")
        self._test_tag = None
        self._tag = None

    def get_memory_io_data_size(self):
        return 100

    def write_data_to_memory_io(self, memory, tag):
        memory.write(struct.pack("<I", tag))
        memory.seek(0)
        self._tag = tag
        self._test_tag = struct.unpack("<I", memory.read(4))[0]

    def test_memory_io(self):
        hostname = "spinn-10.cs.man.ac.uk"
        graph = MachineGraph("Test")
        graph.add_vertex(self)
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
        algorithms = ["OneToOnePlacer", "FrontEndCommonWriteMemoryIOData"]
        executor = PACMANAlgorithmExecutor(
            algorithms, [], inputs, [],
            xml_paths=(
                helpful_functions.get_front_end_common_pacman_xml_paths()),
            packages=(
                helpful_functions.get_front_end_common_pacman_packages()))
        executor.execute_mapping()
        transceiver.stop_application(30)
        transceiver.close()
        self.assertEqual(self._test_tag, self._tag, "Tag is not equal")
