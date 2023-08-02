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
from spinn_utilities.overrides import overrides
from spinn_machine.tags import IPTag, ReverseIPTag
from pacman.model.tags import Tags
from pacman.model.graphs.machine import SimpleMachineVertex
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.interface_functions import tags_loader
from spinnman.transceiver.mockable_transceiver import MockableTransceiver


class _MockTransceiver(MockableTransceiver):

    def __init__(self):
        self._ip_tags = list()
        self._reverse_ip_tags = list()

    @overrides(MockableTransceiver.set_ip_tag)
    def set_ip_tag(self, ip_tag, use_sender=False):
        self._ip_tags.append(ip_tag)

    @overrides(MockableTransceiver.set_reverse_ip_tag)
    def set_reverse_ip_tag(self, reverse_ip_tag):
        self._reverse_ip_tags.append(reverse_ip_tag)


class TestFrontEndCommonTagsLoader(unittest.TestCase):

    def setUp(self):
        unittest_setup()

    def test_call(self):
        """ Test calling the tags loader
        """
        writer = FecDataWriter.mock()
        vertex = SimpleMachineVertex(None)

        tag_1 = IPTag("127.0.0.1", 0, 0, 1, "localhost", 12345, True, "Test")
        tag_2 = IPTag("127.0.0.1", 0, 0, 2, "localhost", 54321, True, "Test")
        rip_tag_1 = ReverseIPTag("127.0.0.1", 3, 12345, 0, 0, 0, 0)
        rip_tag_2 = ReverseIPTag("127.0.0.1", 4, 12346, 0, 0, 0, 0)

        tags = Tags()
        tags.add_ip_tag(tag_1, vertex)
        tags.add_ip_tag(tag_2, vertex)
        tags.add_reverse_ip_tag(rip_tag_1, vertex)
        tags.add_reverse_ip_tag(rip_tag_2, vertex)
        writer.set_tags(tags)
        txrx = _MockTransceiver()
        writer.set_transceiver(txrx)

        tags_loader()
        # Note the values being tested are only in the MockTransceiver
        self.assertIn(tag_1, txrx._ip_tags)
        self.assertIn(tag_2, txrx._ip_tags)
        self.assertIn(rip_tag_1, txrx._reverse_ip_tags)
        self.assertIn(rip_tag_2, txrx._reverse_ip_tags)


if __name__ == '__main__':
    unittest.main()
