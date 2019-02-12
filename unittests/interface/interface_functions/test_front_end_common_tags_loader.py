import unittest
from spinn_machine.tags import IPTag, ReverseIPTag
from pacman.model.tags import Tags
from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import ResourceContainer
from spinn_front_end_common.interface.interface_functions import TagsLoader


class _MockTransceiver(object):

    def __init__(self):
        self._ip_tags = list()
        self._reverse_ip_tags = list()

    def set_ip_tag(self, ip_tag):
        self._ip_tags.append(ip_tag)

    def set_reverse_ip_tag(self, reverse_ip_tag):
        self._reverse_ip_tags.append(reverse_ip_tag)

    def clear_ip_tag(self, tag):
        pass

    @property
    def ip_tags(self):
        return self._ip_tags

    @property
    def reverse_ip_tags(self):
        return self._reverse_ip_tags


class _TestVertex(MachineVertex):
    def resources_required(self):
        return ResourceContainer(0)


class TestFrontEndCommonTagsLoader(unittest.TestCase):

    def test_call(self):
        """ Test calling the tags loader
        """

        vertex = _TestVertex()

        tag_1 = IPTag("127.0.0.1", 0, 0, 1, "localhost", 12345, True, "Test")
        tag_2 = IPTag("127.0.0.1", 0, 0, 2, "localhost", 54321, True, "Test")
        rip_tag_1 = ReverseIPTag("127.0.0.1", 3, 12345, 0, 0, 0, 0)
        rip_tag_2 = ReverseIPTag("127.0.0.1", 4, 12346, 0, 0, 0, 0)

        tags = Tags()
        tags.add_ip_tag(tag_1, vertex)
        tags.add_ip_tag(tag_2, vertex)
        tags.add_reverse_ip_tag(rip_tag_1, vertex)
        tags.add_reverse_ip_tag(rip_tag_2, vertex)

        txrx = _MockTransceiver()

        loader = TagsLoader()
        loader.__call__(txrx, tags)
        self.assertIn(tag_1, txrx.ip_tags)
        self.assertIn(tag_2, txrx.ip_tags)
        self.assertIn(rip_tag_1, txrx.reverse_ip_tags)
        self.assertIn(rip_tag_2, txrx.reverse_ip_tags)


if __name__ == '__main__':
    unittest.main()
