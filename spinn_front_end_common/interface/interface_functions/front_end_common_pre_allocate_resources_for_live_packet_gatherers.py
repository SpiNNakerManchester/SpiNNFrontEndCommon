# spinn front end common imports
from pacman.model.resources.core_resource import CoreResource
from pacman.model.resources.pre_allocated_resource_container import \
    PreAllocatedResourceContainer
from pacman.model.resources.specific_chip_sdram_resource import \
    SpecificChipSDRAMResource
from spinn_front_end_common.utility_models.live_packet_gather_machine_vertex \
    import LivePacketGatherMachineVertex
from spinn_utilities.progress_bar import ProgressBar


class FrontEndCommonPreAllocateResourcesForLivePacketGatherers(object):
    """ Adds Live Packet Gatherer resources as required for a machine
    """

    def __call__(
            self, live_packet_gatherer_parameters, machine,
            pre_allocated_resources=None):
        """

        :param live_packet_gatherer_parameters:\
            the LPG parameters requested by the script
        :param previous_allocated_resources: other pre-allocated resources
        :param machine: the spinnaker machine as discovered
        :return: pre allocated resources
        """

        progress_bar = ProgressBar(
            len(machine.ethernet_connected_chips),
            "Preallocating resources for Live Recording")

        # store how much SDRAM the LPG uses per core
        lpg_sdram_requirement = LivePacketGatherMachineVertex.get_sdram_usage()

        # for every Ethernet connected chip, get the resources needed by the
        # live packet gatherers
        sdrams = list()
        cores = list()
        for chip in progress_bar.over(machine.ethernet_connected_chips):
            sdram_requirements = 0
            core_requirements = 0

            for live_packet_gatherer_params in live_packet_gatherer_parameters:
                if (live_packet_gatherer_params.board_address is None or
                    live_packet_gatherer_params.board_address ==
                        chip.ip_address):
                    sdram_requirements += lpg_sdram_requirement
                    core_requirements += 1
            if sdram_requirements > 0:
                sdrams.append(
                    SpecificChipSDRAMResource(chip, sdram_requirements))
            if core_requirements > 0:
                cores.append(CoreResource(chip, core_requirements))

        # create pre allocated resource container
        lpg_pre_allocated_resource_container = PreAllocatedResourceContainer(
            specific_sdram_usage=sdrams, core_resources=cores)

        # add other pre allocated resources
        if pre_allocated_resources is not None:
            lpg_pre_allocated_resource_container.extend(
                pre_allocated_resources)

        # end progress bar
        progress_bar.end()

        # return pre allocated resources
        return lpg_pre_allocated_resource_container
