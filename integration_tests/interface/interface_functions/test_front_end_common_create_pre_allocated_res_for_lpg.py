from pacman.model.resources.core_resource import CoreResource
from pacman.model.resources.pre_allocated_resource_container import \
    PreAllocatedResourceContainer
from pacman.model.resources.specific_chip_sdram_resource import \
    SpecificChipSDRAMResource
from spinn_front_end_common.interface.interface_functions.\
    front_end_common_pre_allocate_resources_for_live_packet_gatherers import \
    FrontEndCommonPreAllocateResourcesForLivePacketGatherers
from spinn_front_end_common.utilities.utility_objs. \
    live_packet_gather_parameters import \
    LivePacketGatherParameters
from spinn_front_end_common.utility_models. \
    live_packet_gather_machine_vertex import \
    LivePacketGatherMachineVertex
from spinn_machine.virtual_machine import VirtualMachine
from spinnman.messages.eieio.eieio_type import EIEIOType


class TestLPGPreAllocateRes(object):
    """ tests the interaction of the pre resource calcs

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
            'tag': None,
            'label': "bupkis"}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        extended = dict(default_params)
        extended.update({'partition_id': "EVENTS"})
        default_params_holder = LivePacketGatherParameters(**extended)
        live_packet_gatherers[default_params_holder] = list()

        # run  pre allocator
        pre_alloc = FrontEndCommonPreAllocateResourcesForLivePacketGatherers()
        pre_res = pre_alloc(
            live_packet_gatherers=live_packet_gatherers, machine=machine,
            previous_allocated_resources=PreAllocatedResourceContainer())

        locs = list()
        locs.append((0, 0))
        locs.append((4, 8))
        locs.append((8, 4))

        # verify sdram
        sdrams = pre_res.specific_sdram_usage
        for sdram in sdrams:
            locs.remove((sdram.chip.x, sdram.chip.y))
            if sdram.sdram_usage != \
                    LivePacketGatherMachineVertex.get_sdram_usage():
                raise Exception
        if len(locs) != 0:
            raise Exception


        locs = list()
        locs.append((0, 0))
        locs.append((4, 8))
        locs.append((8, 4))
        # verify cores
        cores = pre_res.core_resources
        for core in cores:
            locs.remove((core.chip.x, core.chip.y))
            if core.n_cores != 1:
                raise Exception
        if len(locs) != 0:
            raise Exception

        # verify specific cores
        if len(pre_res.specific_cores_resource) != 0:
            raise Exception

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
            'tag': None,
            'label': "bupkis"}

        # data stores needed by algorithm
        live_packet_gatherers = dict()
        extended = dict(default_params)
        extended.update({'partition_id': "EVENTS"})
        default_params_holder = LivePacketGatherParameters(**extended)
        live_packet_gatherers[default_params_holder] = list()

        # and special LPG on ethernet connected chips
        index = 1
        specific_data_holders = dict()
        for chip in machine.ethernet_connected_chips:
            extended['label'] = "bupkis{}".format(index)
            extended['board_address'] = chip.ip_address
            default_params_holder2 = LivePacketGatherParameters(**extended)
            specific_data_holders[(chip.x, chip.y)] = default_params_holder2
            live_packet_gatherers[default_params_holder2] = list()

        pre_alloc = FrontEndCommonPreAllocateResourcesForLivePacketGatherers()
        pre_res = pre_alloc(
            live_packet_gatherers=live_packet_gatherers, machine=machine,
            previous_allocated_resources=PreAllocatedResourceContainer())

        locs = list()
        locs.append((0, 0))
        locs.append((4, 8))
        locs.append((8, 4))

        # verify sdram
        sdrams = pre_res.specific_sdram_usage
        for sdram in sdrams:
            locs.remove((sdram.chip.x, sdram.chip.y))
            if sdram.sdram_usage != \
                    LivePacketGatherMachineVertex.get_sdram_usage() * 2:
                raise Exception
        if len(locs) != 0:
            raise Exception

        locs = dict()
        locs[(0, 0)] = 0
        locs[(4, 8)] = 0
        locs[(8, 4)] = 0
        # verify cores
        cores = pre_res.core_resources
        for core in cores:
            locs[(core.chip.x, core.chip.y)] += core.n_cores

        if locs[(0, 0)] != 2 or locs[(4, 8)] != 2 or locs[(8, 4)] != 2:
            raise Exception

        # verify specific cores
        if len(pre_res.specific_cores_resource) != 0:
            raise Exception

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
            'tag': None,
            'label': "bupkis"}

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
        pre_alloc = FrontEndCommonPreAllocateResourcesForLivePacketGatherers()
        pre_res = pre_alloc(
            live_packet_gatherers=live_packet_gatherers, machine=machine,
            previous_allocated_resources=pre_pre_res)

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
                if sdram.chip.x == 2 and sdram.chip.y == 2:
                    if sdram.sdram_usage != 30000:
                        raise Exception
                elif sdram.chip.x == 7 and sdram.chip.y == 7:
                    if sdram.sdram_usage != 50000:
                        raise Exception
                else:
                    raise Exception
        if len(locs) != 0:
            raise Exception

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
                if core.chip.x == 3 and core.chip.y == 3:
                    if core.n_cores != 2:
                        raise Exception
                else:
                    raise Exception
        if len(locs) != 0:
            raise Exception

        # verify specific cores
        if len(pre_res.specific_cores_resource) != 0:
            raise Exception

    def test_none(self):
        machine = VirtualMachine(width=12, height=12, with_wrap_arounds=True)
        live_packet_gatherers = dict()
        # run  pre allocator
        pre_alloc = FrontEndCommonPreAllocateResourcesForLivePacketGatherers()
        pre_res = pre_alloc(
            live_packet_gatherers=live_packet_gatherers, machine=machine,
            previous_allocated_resources=PreAllocatedResourceContainer())
        if (len(pre_res.specific_cores_resource) != 0 or
                len(pre_res.core_resources) != 0 or
                len(pre_res.specific_sdram_usage) != 0):
            raise Exception

    def test_fail(self):
        machine = VirtualMachine(width=12, height=12, with_wrap_arounds=True)
        live_packet_gatherers = dict()
        pre_alloc = FrontEndCommonPreAllocateResourcesForLivePacketGatherers()
        try:
            pre_res = pre_alloc(
                live_packet_gatherers=live_packet_gatherers, machine=machine,
                previous_allocated_resources=None)
            raise Exception
        except Exception:
            pass

if __name__ == "__main__":
    test = TestLPGPreAllocateRes()
    test.test_one_lpg_params()
    test.test_one_lpg_params_and_3_specific()
    test.test_added_pre_res()
    test.test_none()
    test.test_fail()

