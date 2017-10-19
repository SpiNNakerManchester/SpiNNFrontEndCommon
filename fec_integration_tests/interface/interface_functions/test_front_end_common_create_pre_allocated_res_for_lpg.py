from pacman.model.resources import CoreResource
from pacman.model.resources import PreAllocatedResourceContainer
from pacman.model.resources import SpecificChipSDRAMResource
from spinn_front_end_common.interface.interface_functions import \
    PreAllocateResourcesForLivePacketGatherers
from spinn_front_end_common.utilities.utility_objs import \
    LivePacketGatherParameters
from spinn_front_end_common.utility_models import \
    LivePacketGatherMachineVertex
from spinn_machine import VirtualMachine
from spinnman.messages.eieio import EIEIOType

import unittest


class TestLPGPreAllocateRes(unittest.TestCase):
    """ tests the interaction of the pre resource calculations

    """

    def test_one_lpg_params(self):
        machine = VirtualMachine(width=12, height=12, with_wrap_arounds=True)

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
            'board_address': None,
            'tag': None}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        extended = dict(default_params)
        extended.update({'partition_id': "EVENTS"})
        default_params_holder = LivePacketGatherParameters(**extended)
        live_packet_gatherers[default_params_holder] = list()

        # run  pre allocator
        pre_alloc = PreAllocateResourcesForLivePacketGatherers()
        pre_res = pre_alloc(
            live_packet_gatherer_parameters=live_packet_gatherers,
            machine=machine)

        locs = list()
        locs.append((0, 0))
        locs.append((4, 8))
        locs.append((8, 4))

        # verify sdram
        sdrams = pre_res.specific_sdram_usage
        for sdram in sdrams:
            locs.remove((sdram.chip.x, sdram.chip.y))
            self.assertEqual(
                sdram.sdram_usage,
                LivePacketGatherMachineVertex.get_sdram_usage())
        self.assertEqual(len(locs), 0)

        locs = list()
        locs.append((0, 0))
        locs.append((4, 8))
        locs.append((8, 4))
        # verify cores
        cores = pre_res.core_resources
        for core in cores:
            locs.remove((core.chip.x, core.chip.y))
            self.assertEqual(core.n_cores, 1)
        self.assertEqual(len(locs), 0)

        # verify specific cores
        self.assertEqual(len(pre_res.specific_core_resources), 0)

    def test_one_lpg_params_and_3_specific(self):
        machine = VirtualMachine(width=12, height=12, with_wrap_arounds=True)

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
            'board_address': None,
            'tag': None}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        extended = dict(default_params)
        extended.update({'partition_id': "EVENTS"})
        default_params_holder = LivePacketGatherParameters(**extended)
        live_packet_gatherers[default_params_holder] = list()

        # and special LPG on Ethernet connected chips
        for chip in machine.ethernet_connected_chips:
            extended['board_address'] = chip.ip_address
            default_params_holder2 = LivePacketGatherParameters(**extended)
            live_packet_gatherers[default_params_holder2] = list()

        pre_alloc = PreAllocateResourcesForLivePacketGatherers()
        pre_res = pre_alloc(
            live_packet_gatherer_parameters=live_packet_gatherers,
            machine=machine)

        locs = list()
        locs.append((0, 0))
        locs.append((4, 8))
        locs.append((8, 4))

        # verify sdram
        sdrams = pre_res.specific_sdram_usage
        for sdram in sdrams:
            locs.remove((sdram.chip.x, sdram.chip.y))
            self.assertEqual(
                sdram.sdram_usage,
                LivePacketGatherMachineVertex.get_sdram_usage() * 2)
        self.assertEqual(len(locs), 0)

        locs = dict()
        locs[(0, 0)] = 0
        locs[(4, 8)] = 0
        locs[(8, 4)] = 0

        # verify cores
        cores = pre_res.core_resources
        for core in cores:
            locs[(core.chip.x, core.chip.y)] += core.n_cores

        for (x, y) in [(0, 0), (4, 8), (8, 4)]:
            self.assertEqual(locs[x, y], 2)

        # verify specific cores
        self.assertEqual(len(pre_res.specific_core_resources), 0)

    def test_added_pre_res(self):
        machine = VirtualMachine(width=12, height=12, with_wrap_arounds=True)

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
            'board_address': None,
            'tag': None}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        extended = dict(default_params)
        extended.update({'partition_id': "EVENTS"})
        default_params_holder = LivePacketGatherParameters(**extended)
        live_packet_gatherers[default_params_holder] = list()

        # create pre res
        sdram_requirements = {machine.get_chip_at(2, 2): 30000,
                              machine.get_chip_at(7, 7): 50000}
        core_requirements = {machine.get_chip_at(3, 3): 2}

        sdrams = list()
        cores = list()
        for chip in sdram_requirements:
            sdrams.append(SpecificChipSDRAMResource(
                chip, sdram_requirements[chip]))
        for chip in core_requirements:
            cores.append(CoreResource(chip, core_requirements[chip]))
        pre_pre_res = PreAllocatedResourceContainer(
            core_resources=cores, specific_sdram_usage=sdrams)

        # run  pre allocator
        pre_alloc = PreAllocateResourcesForLivePacketGatherers()
        pre_res = pre_alloc(
            live_packet_gatherer_parameters=live_packet_gatherers,
            machine=machine, pre_allocated_resources=pre_pre_res)

        locs = list()
        locs.append((0, 0))
        locs.append((4, 8))
        locs.append((8, 4))
        locs.append((2, 2))
        locs.append((7, 7))

        # verify sdram
        sdrams = pre_res.specific_sdram_usage
        for sdram in sdrams:
            locs.remove((sdram.chip.x, sdram.chip.y))
            if sdram.sdram_usage != \
                    LivePacketGatherMachineVertex.get_sdram_usage():
                self.assertIn(sdram.chip.x, (2, 7))
                self.assertIn(sdram.chip.y, (2, 7))
                self.assertEqual(sdram.chip.x, sdram.chip.y)
                if sdram.chip.x == 2 and sdram.chip.y == 2:
                    self.assertEqual(sdram.sdram_usage, 30000)
                elif sdram.chip.x == 7 and sdram.chip.y == 7:
                    self.assertEqual(sdram.sdram_usage, 50000)
        self.assertEqual(len(locs), 0)

        locs = list()
        locs.append((0, 0))
        locs.append((4, 8))
        locs.append((8, 4))
        locs.append((3, 3))

        # verify cores
        cores = pre_res.core_resources
        for core in cores:
            locs.remove((core.chip.x, core.chip.y))
            if core.n_cores != 1:
                self.assertEqual(core.chip.x, 3)
                self.assertEqual(core.chip.y, 3)
                self.assertEqual(core.n_cores, 2)
        self.assertEqual(len(locs), 0)

        # verify specific cores
        self.assertEqual(len(pre_res.specific_core_resources), 0)

    def test_none(self):
        machine = VirtualMachine(width=12, height=12, with_wrap_arounds=True)
        live_packet_gatherers = dict()
        # run  pre allocator
        pre_alloc = PreAllocateResourcesForLivePacketGatherers()
        pre_res = pre_alloc(
            live_packet_gatherer_parameters=live_packet_gatherers,
            machine=machine)
        self.assertEqual(len(pre_res.specific_core_resources), 0)
        self.assertEqual(len(pre_res.core_resources), 0)
        self.assertEqual(len(pre_res.specific_sdram_usage), 0)

    def test_fail(self):
        machine = VirtualMachine(width=12, height=12, with_wrap_arounds=True)
        live_packet_gatherers = dict()
        pre_alloc = PreAllocateResourcesForLivePacketGatherers()
        self.assertRaises(
            Exception, pre_alloc(
                live_packet_gatherer_parameters=live_packet_gatherers,
                machine=machine))


if __name__ == "__main__":
    unittest.main()
