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
from spinn_machine import virtual_machine
from spinnman.messages.eieio import EIEIOType
from pacman.model.resources import PreAllocatedResourceContainer
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.interface_functions import (
    preallocate_resources_for_live_packet_gatherers)
from spinn_front_end_common.utilities.utility_objs import (
    LivePacketGatherParameters)
from spinn_front_end_common.utility_models import (
    LivePacketGatherMachineVertex)


class TestLPGPreAllocateRes(unittest.TestCase):
    """ tests the interaction of the pre resource calculations
    """
    def setUp(self):
        unittest_setup()

    def test_one_lpg_params(self):
        machine = virtual_machine(width=12, height=12)

        default_params = {
            'use_prefix': False,
            'key_prefix': None,
            'prefix_type': None,
            'message_type': EIEIOType.KEY_32_BIT,
            'right_shift': 0,
            'payload_as_time_stamps': True,
            'use_payload_prefix': True,
            'payload_prefix': None,
            'payload_right_shift': 0,
            'number_of_packets_sent_per_time_step': 0,
            'hostname': None,
            'port': None,
            'strip_sdp': None,
            'tag': None,
            'label': "Test"}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        default_params_holder = LivePacketGatherParameters(**default_params)
        live_packet_gatherers[default_params_holder] = list()

        # run  pre allocator
        pre_res = preallocate_resources_for_live_packet_gatherers(
            live_packet_gatherer_parameters=live_packet_gatherers,
            pre_allocated_resources=PreAllocatedResourceContainer())

        # verify sdram
        self.assertEqual(
            pre_res.sdram_all.get_total_sdram(0), 0)
        self.assertEqual(
            pre_res.sdram_ethernet.get_total_sdram(0),
            LivePacketGatherMachineVertex.get_sdram_usage())

        self.assertEqual(pre_res.cores_all, 0)
        self.assertEqual(pre_res.cores_ethernet, 1)

    def test_none(self):
        machine = virtual_machine(width=12, height=12)
        live_packet_gatherers = dict()
        # run  pre allocator
        pre_res = preallocate_resources_for_live_packet_gatherers(
            live_packet_gatherer_parameters=live_packet_gatherers,
            pre_allocated_resources=PreAllocatedResourceContainer())
        self.assertEqual(
            pre_res.sdram_all.get_total_sdram(0), 0)
        self.assertEqual(
            pre_res.sdram_ethernet.get_total_sdram(0), 0)

        self.assertEqual(pre_res.cores_all, 0)
        self.assertEqual(pre_res.cores_ethernet, 0)

    def test_fail(self):
        machine = virtual_machine(width=12, height=12)
        live_packet_gatherers = {'foo': 'bar'}
        with self.assertRaises(Exception) as exn:
            preallocate_resources_for_live_packet_gatherers(
                live_packet_gatherer_parameters=live_packet_gatherers,
                pre_allocated_resources=PreAllocatedResourceContainer())
        # Make sure we know what the exception was; NOT an important test!
        self.assertEqual(
            "'str' object has no attribute 'hostname'",
            str(exn.exception))


if __name__ == "__main__":
    unittest.main()
