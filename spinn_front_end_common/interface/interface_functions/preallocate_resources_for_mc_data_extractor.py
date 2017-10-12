from pacman.model.resources import SpecificChipSDRAMResource, CoreResource, \
    PreAllocatedResourceContainer
from pacman.model.resources.specific_board_iptag_resource import \
    SpecificBoardTagResource
from spinn_front_end_common.utility_models.\
    multicast_data_speed_up_packet_gatherer_machine_vertex import \
    MulticastDataSpeedUpPacketGatherMachineVertex
from spinn_utilities.progress_bar import ProgressBar
from spinnman.connections.udp_packet_connections import UDPConnection


class PreAllocateResourcesForMCDataExtractor(object):

    def __call__(
            self, machine, pre_allocated_resources=None,
            n_cores_to_allocate=1):
        """

        :param machine: spinnaker machine object
        :param pre_allocated_resources: resoruces already pre allocated
        :param n_cores_to_allocate: config parasm for how many gatherers to use
        """

        progress = ProgressBar(
            len(machine.ethernet_connected_chips),
            "Preallocating resources for Data Extraction Speed Up")

        connection = UDPConnection(local_host=None)
        connection_mapping = dict()

        # get resources from packet gatherer
        resources = \
            MulticastDataSpeedUpPacketGatherMachineVertex.\
            resources_required_for_connection(connection)

        sdrams = list()
        cores = list()
        tags = list()

        # locate ethernet connected chips that the vertices reside on
        for ethernet_connected_chip in \
                progress.over(machine.ethernet_connected_chips):

            # do resources. sdram, cores, tags
            sdrams.append(SpecificChipSDRAMResource(
                chip=ethernet_connected_chip,
                sdram_usage=resources.sdram.size))
            cores.append(CoreResource(
                chip=ethernet_connected_chip, n_cores=n_cores_to_allocate))
            tags.append(SpecificBoardTagResource(
                board=ethernet_connected_chip.ip_address,
                ip_address=resources.iptags[0].ip_address,
                port=resources.iptags[0].port,
                strip_sdp=resources.iptags[0].strip_sdp,
                tag=resources.iptags[0].tag,
                traffic_identifier=resources.iptags[0].traffic_identifier))
            connection_mapping[(ethernet_connected_chip.x,
                                ethernet_connected_chip.y)] = connection

        # create pre allocated resource container
        data_speed_up_prealloc_resource_container = \
            PreAllocatedResourceContainer(
                specific_sdram_usage=sdrams, core_resources=cores,
                specific_iptag_resources=tags)

        # add other pre allocated resources
        if pre_allocated_resources is not None:
            data_speed_up_prealloc_resource_container.extend(
                pre_allocated_resources)

        # return pre allocated resources
        return data_speed_up_prealloc_resource_container, connection_mapping
