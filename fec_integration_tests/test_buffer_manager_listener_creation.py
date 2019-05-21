import tempfile
import unittest
from spinn_utilities.overrides import overrides
from pacman.model.placements import Placement, Placements
from pacman.model.tags import Tags
from pacman.model.graphs.application import ApplicationVertex
from spinn_machine.tags import IPTag
from spinnman.transceiver import Transceiver
from spinnman.connections.udp_packet_connections import (
    SCAMPConnection, EIEIOConnection)
from spinn_front_end_common.interface.buffer_management import BufferManager


class TestBufferManagerListenerCreation(unittest.TestCase):

    def test_listener_creation(self):
        # Test of buffer manager listener creation problem, where multiple
        # listeners were being created for the buffer manager traffic from
        # individual boards, where it's preferred all traffic is received by
        # a single listener

        # Create two vertices
        v1 = _TestVertex(10, "v1", 256)
        v2 = _TestVertex(10, "v2", 256)

        # Create two tags - important thing is port=None
        t1 = IPTag(board_address='127.0.0.1', destination_x=0,
                   destination_y=1, tag=1, port=None, ip_address=None,
                   strip_sdp=True, traffic_identifier='BufferTraffic')
        t2 = IPTag(board_address='127.0.0.1', destination_x=0,
                   destination_y=2, tag=1, port=None, ip_address=None,
                   strip_sdp=True, traffic_identifier='BufferTraffic')

        # Create 'Tags' object and add tags
        t = Tags()
        t.add_ip_tag(t1, v1)
        t.add_ip_tag(t2, v2)

        # Create board connections
        connections = []
        connections.append(SCAMPConnection(
            remote_host=None))
        connections.append(EIEIOConnection())

        # Create two placements and 'Placements' object
        pl1 = Placement(v1, 0, 1, 1)
        pl2 = Placement(v2, 0, 2, 1)
        pl = Placements([pl1, pl2])

        # Create transceiver
        trnx = Transceiver(version=5, connections=connections)
        # Alternatively, one can register a udp listener for testing via:
        # trnx.register_udp_listener(callback=None,
        #        connection_class=EIEIOConnection)

        testdir = tempfile.mkdtemp()
        print(testdir)
        # Create buffer manager
        bm = BufferManager(
            placements=pl, tags=t, transceiver=trnx, extra_monitor_cores=None,
            packet_gather_cores_to_ethernet_connection_map=None,
            extra_monitor_to_chip_mapping=None, machine=None,
            fixed_routes=None, uses_advanced_monitors=True,
            report_folder=testdir)

        # Register two listeners, and check the second listener uses the
        # first rather than creating a new one
        bm._add_buffer_listeners(vertex=v1)
        bm._add_buffer_listeners(vertex=v2)

        number_of_listeners = 0
        for i in bm._transceiver._udp_listenable_connections_by_class[
                EIEIOConnection]:
            # Check if listener is registered on connection - we only expect
            # one listener to be registered, as all connections can use the
            # same listener for the buffer manager
            if not i[1] is None:
                number_of_listeners += 1
            print(i)
        self.assertEqual(number_of_listeners, 1)


class _TestVertex(ApplicationVertex):
    """
    taken skeleton test vertex definition from PACMAN.uinit_test_objects
    """
    _model_based_max_atoms_per_core = None

    def __init__(self, n_atoms, label=None, max_atoms_per_core=256):
        super(_TestVertex, self).__init__(
            label=label, max_atoms_per_core=max_atoms_per_core)
        self._model_based_max_atoms_per_core = max_atoms_per_core
        self._n_atoms = n_atoms

    @overrides
    def get_resources_used_by_atoms(self, vertex_slice):
        pass

    @overrides(ApplicationVertex.create_machine_vertex)
    def create_machine_vertex(
            self, vertex_slice, resources_required, label=None,
            constraints=None):
        pass

    @property
    @overrides(ApplicationVertex.n_atoms)
    def n_atoms(self):
        return self._n_atoms


if __name__ == "__main__":
    unittest.main()
