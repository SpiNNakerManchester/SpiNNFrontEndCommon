# spinn front end common imports
from pacman.model.resources import CoreResource
from pacman.model.resources import PreAllocatedResourceContainer
from pacman.model.resources import SpecificChipSDRAMResource
from spinn_front_end_common.utility_models.live_packet_gather_machine_vertex \
    import LivePacketGatherMachineVertex as LPGVertex
from spinn_utilities.progress_bar import ProgressBar


class PreAllocateResourcesForLivePacketGatherers(object):
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

        progress = ProgressBar(
            len(machine.ethernet_connected_chips),
            "Preallocating resources for Live Recording")

        # store how much SDRAM the LPG uses per core
        lpg_sdram_requirement = LPGVertex.get_sdram_usage()

        # for every Ethernet connected chip, get the resources needed by the
        # live packet gatherers
        sdrams = list()
        cores = list()
        for chip in progress.over(machine.ethernet_connected_chips):
            self._add_chip_lpg_reqs(live_packet_gatherer_parameters, chip,
                                    lpg_sdram_requirement, sdrams, cores)

        # create pre allocated resource container
        lpg_prealloc_resource_container = PreAllocatedResourceContainer(
            specific_sdram_usage=sdrams, core_resources=cores)

        # add other pre allocated resources
        if pre_allocated_resources is not None:
            lpg_prealloc_resource_container.extend(pre_allocated_resources)

        # return pre allocated resources
        return lpg_prealloc_resource_container

    @staticmethod
    def _add_chip_lpg_reqs(lpg_parameters, chip, lpg_sdram, sdrams, cores):
        sdram_reqs = 0
        core_reqs = 0

        for lpg_params in lpg_parameters:
            if (lpg_params.board_address is None or
                    lpg_params.board_address == chip.ip_address):
                sdram_reqs += lpg_sdram
                core_reqs += 1

        if sdram_reqs > 0:
            sdrams.append(SpecificChipSDRAMResource(chip, sdram_reqs))
        if core_reqs > 0:
            cores.append(CoreResource(chip, core_reqs))
