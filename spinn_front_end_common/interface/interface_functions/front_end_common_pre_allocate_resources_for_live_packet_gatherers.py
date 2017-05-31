# spinn front end common imports
from pacman.model.resources.core_resource import CoreResource
from pacman.model.resources.pre_allocated_resource_container import \
    PreAllocatedResourceContainer
from pacman.model.resources.specific_chip_sdram_resource import \
    SpecificChipSDRAMResource
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utility_models.live_packet_gather_machine_vertex \
    import LivePacketGatherMachineVertex
from spinn_utilities.progress_bar import ProgressBar


class FrontEndCommonPreAllocateResourcesForLivePacketGatherers(object):
    """ function to add LPG resources as required for a machine

    """

    def __call__(
            self, live_packet_gatherers, previous_allocated_resources,
            machine):
        """ call that adds LPG vertices on ethernet connected chips as 
        required. 

        :param live_packet_gatherers: the LPG parameters requested by the \
        script
        :param previous_allocated_resources: other pre-allocated resources
        :param machine: the spinnaker machine as discovered
        :return: pre allocated resources 
        """

        sdram_requirements = dict()
        core_requirements = dict()

        progress_bar = ProgressBar(
            total_number_of_things_to_do=
            len(live_packet_gatherers) * len(machine.ethernet_connected_chips),
            string_describing_what_being_progressed=
            "pre allocating LPG resources")

        # clone the live_packet_gatherer parameters holder for usage
        working_live_packet_gatherers_parameters = dict(live_packet_gatherers)

        # store how much SDRAM the LPG uses per core
        lpg_sdram_requirement = LivePacketGatherMachineVertex.get_sdram_usage()

        # locate LPG's which have specific board addresses to their ethernet
        # connected chips.
        board_specific_lpgs = list()
        for live_packet_gatherer_params in \
                working_live_packet_gatherers_parameters:
            if live_packet_gatherer_params.board_address is not None:
                board_specific_lpgs.append(live_packet_gatherer_params)

        # add LPG's which have specific board addresses
        for board_specific_lpg_params in board_specific_lpgs:
            chip = self._get_ethernet_chip(
                machine, board_specific_lpg_params.board_address)
            self._allocate_resources(
                sdram_requirements, core_requirements, chip,
                lpg_sdram_requirement)
            del working_live_packet_gatherers_parameters[
                board_specific_lpg_params]
            progress_bar.update()

        # for ever ethernet connected chip, add the rest of the LPG types
        for chip in machine.ethernet_connected_chips:
            for _ in working_live_packet_gatherers_parameters:
                self._allocate_resources(
                    sdram_requirements, core_requirements, chip,
                    lpg_sdram_requirement)
                progress_bar.update()

        # create pre allocated resource container elements
        sdrams = list()
        cores = list()
        for chip in sdram_requirements:
            sdrams.append(SpecificChipSDRAMResource(
                chip, sdram_requirements[chip]))
        for chip in core_requirements:
            cores.append(CoreResource(chip, core_requirements[chip]))

        # create pre allocated resource container
        lpg_pre_allocated_resource_container = PreAllocatedResourceContainer(
            specific_sdram_usage=sdrams, core_resources=cores)

        # add other pre allocated resources
        lpg_pre_allocated_resource_container.extend(
            previous_allocated_resources)

        # end progress bar
        progress_bar.end()

        # return pre allocated resources
        return lpg_pre_allocated_resource_container

    @staticmethod
    def _allocate_resources(
            sdram_requirements, core_requirements, chip,
            lpg_sdram_requirement):
        """ allocates resources for lpg
        
        :param sdram_requirements: sdram holder
        :param core_requirements: core holder
        :param chip:  chip to allocate on
        :param lpg_sdram_requirement: the sdram requirements of a LPG
        :rtype: None 
        """
        if chip in sdram_requirements:
            sdram_requirements[chip] += lpg_sdram_requirement
        else:
            sdram_requirements[chip] = lpg_sdram_requirement
        if chip in core_requirements:
            core_requirements[chip] += 1
        else:
            core_requirements[chip] = 1

    @staticmethod
    def _get_ethernet_chip(machine, board_address):
        """ locate the chip which supports a given board address (aka its 
        ip_address)

        :param machine: the spinnaker machine 
        :param board_address:  the board address to locate the chip of.
        :return: The chip that supports that board address
        :raises ConfigurationException: when that board address has no chip\
        associated with it
        """
        for chip in machine.ethernet_connected_chips:
            if chip.ip_address == board_address:
                return chip
        raise exceptions.ConfigurationException(
            "cannot find the ethernet connected chip which supports the "
            "board address {}".format(board_address))
