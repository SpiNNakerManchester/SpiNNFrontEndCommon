from pacman.model.resources import SpecificChipSDRAMResource, CoreResource, \
    PreAllocatedResourceContainer
from pacman.model.resources.specific_board_iptag_resource import \
    SpecificBoardTagResource
from spinn_front_end_common.utility_models.\
    data_speed_up_packet_gatherer_machine_vertex import \
    DataSpeedUpPacketGatherMachineVertex
from spinn_utilities.progress_bar import ProgressBar
from spinnman.connections.udp_packet_connections import UDPConnection


class PreAllocateResourcesForExtraMonitorSupport(object):

    def __call__(
            self, machine, pre_allocated_resources=None,
            n_cores_to_allocate=1):
        """

        :param machine: spinnaker machine object
        :param pre_allocated_resources: resources already pre allocated
        :param n_cores_to_allocate: config params for how many gatherers to use
        """

        progress = ProgressBar(
            len(list(machine.ethernet_connected_chips)) + machine.n_chips,
            "Pre allocating resources for Extra Monitor support vertices")

        connection_mapping = dict()

        sdrams = list()
        cores = list()
        tags = list()

        # add resource requirements for the gatherers on each ethernet
        # connected chip. part of data extraction
        self._handle_packet_gathering_support(
            sdrams, cores, tags, machine, progress, connection_mapping,
            n_cores_to_allocate)

        # add resource requirements for re-injector and reader for data
        # extractor
        self._handle_second_monitor_support(cores, machine, progress)

        # create pre allocated resource container
        extra_monitor_pre_allocations = PreAllocatedResourceContainer(
            specific_sdram_usage=sdrams, core_resources=cores,
            specific_iptag_resources=tags)

        # add other pre allocated resources
        if pre_allocated_resources is not None:
            extra_monitor_pre_allocations.extend(pre_allocated_resources)

        # return pre allocated resources
        return extra_monitor_pre_allocations, connection_mapping

    @staticmethod
    def _handle_second_monitor_support(cores, machine, progress):
        """ adds the second monitor pre allocations, which reflect the\
         re-injector and data extractor support

        :param cores: the storage of core requirements
        :param machine: the spinnMachine instance
        :param progress: the progress bar to operate one
        :rtype: None
        """
        for chip in progress.over(machine.chips):
            cores.append(CoreResource(chip=chip, n_cores=1))

    @staticmethod
    def _handle_packet_gathering_support(
            sdrams, cores, tags, machine, progress, connection_mapping,
            n_cores_to_allocate):
        """ adds the packet gathering functionality tied into the data\
         extractor within each chip

        :param sdrams: the pre-allocated sdram requirement for these vertices
        :param cores: the pre-allocated cores requirement for these vertices
        :param tags: the pre-allocated tags requirement for these vertices
        :param machine: the spinnMachine instance
        :param progress: the progress bar to update as needed
        :param connection_mapping: the mapping between connection and chip
        :param n_cores_to_allocate: how many packet gathers to allocate per \
            chip
        :rtype: None
        """

        connection = UDPConnection(local_host=None)

        # get resources from packet gatherer
        resources = DataSpeedUpPacketGatherMachineVertex. \
            resources_required_for_connection(connection)

        # locate ethernet connected chips that the vertices reside on
        for ethernet_connected_chip in \
                progress.over(machine.ethernet_connected_chips,
                              finish_at_end=False):
            # do resources. sdram, cores, tags
            sdrams.append(SpecificChipSDRAMResource(
                chip=ethernet_connected_chip,
                sdram_usage=resources.sdram.get_value()))
            cores.append(CoreResource(
                chip=ethernet_connected_chip, n_cores=n_cores_to_allocate))
            tags.append(SpecificBoardTagResource(
                board=ethernet_connected_chip.ip_address,
                ip_address=resources.iptags[0].ip_address,
                port=resources.iptags[0].port,
                strip_sdp=resources.iptags[0].strip_sdp,
                tag=resources.iptags[0].tag,
                traffic_identifier=resources.iptags[0].traffic_identifier))
            connection_mapping[ethernet_connected_chip.x,
                               ethernet_connected_chip.y] = connection
