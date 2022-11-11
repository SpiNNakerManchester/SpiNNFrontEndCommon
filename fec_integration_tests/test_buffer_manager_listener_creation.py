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

from pacman.model.placements import Placement, Placements
from pacman.model.tags import Tags
from spinn_machine.tags import IPTag
from spinnman.transceiver import Transceiver
from spinnman.connections.udp_packet_connections import (
    SCAMPConnection, EIEIOConnection)
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.buffer_management import BufferManager
from spinn_front_end_common.interface.config_setup import unittest_setup
from pacman_test_objects import SimpleTestVertex


class TestBufferManagerListenerCreation(unittest.TestCase):

    def setUp(self):
        unittest_setup()

    def test_listener_creation(self):
        # Test of buffer manager listener creation problem, where multiple
        # listeners were being created for the buffer manager traffic from
        # individual boards, where it's preferred all traffic is received by
        # a single listener

        writer = FecDataWriter.mock()
        # Create two vertices
        v1 = SimpleTestVertex(10, "v1", 256)
        v2 = SimpleTestVertex(10, "v2", 256)

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
        writer.set_tags(t)

        # Create board connections
        connections = []
        connections.append(SCAMPConnection(
            remote_host=None))
        connections.append(EIEIOConnection())

        # Create two placements and 'Placements' object
        pl1 = Placement(v1, 0, 1, 1)
        pl2 = Placement(v2, 0, 2, 1)
        writer.set_placements(Placements([pl1, pl2]))

        # Create transceiver
        transceiver = Transceiver(version=5, connections=connections)
        # Should be no connection listeners yet; they're made later
        self.assertEqual(transceiver._num_listeners, 0)
        writer.set_transceiver(transceiver)
        # Alternatively, one can register a udp listener for testing via:
        # trnx.register_eieio_listener(callback=None)

        # Create buffer manager
        bm = BufferManager()

        # Register two listeners, and check the second listener uses the
        # first rather than creating a new one
        bm._add_buffer_listeners(vertex=v1)
        bm._add_buffer_listeners(vertex=v2)

        # Check if a listener is registered in the transceiver - we only expect
        # one listener to be registered, as all connections can use the
        # same listener for the buffer manager
        self.assertEqual(transceiver._num_listeners, 1)


if __name__ == "__main__":
    unittest.main()
