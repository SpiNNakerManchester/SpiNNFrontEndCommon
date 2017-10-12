from pacman.model.resources import SpecificChipSDRAMResource, CoreResource
from spinn_front_end_common.utility_models.\
    multicast_data_speed_up_packet_gatherer_machine_vertex import \
    MulticastDataSpeedUpPacketGatherMachineVertex
from spinn_utilities.progress_bar import ProgressBar


class PreAllocateResourcesForMCDataExtractor(object):

    def __init__(self, machine, pre_allocated_resources=None):
        """

        :param machine: spinnaker machine object
        """

        progress = ProgressBar(
            len(machine.ethernet_connected_chips),
            "Preallocating resources for Data Extraction Speed Up")

        # get resources from packet gatherer
        resources = \
            MulticastDataSpeedUpPacketGatherMachineVertex.resources_required

        sdrams = list()
        cores = list()
        tags = list()

        # locate ethernet connected chips that the vertices reside on
        for ethernet_connected_chip in machine.ethernet_connected_chips:
            # do resources. sdram, cores, tags
            sdrams.append(SpecificChipSDRAMResource(
                chip=ethernet_connected_chip,
                sdram_usage=resources.sdram.size))
            cores.append(CoreResource(chip=ethernet_connected_chip, n_cores=1))
            tags.append()
