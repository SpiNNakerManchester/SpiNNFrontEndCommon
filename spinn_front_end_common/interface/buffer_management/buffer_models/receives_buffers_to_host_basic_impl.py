# pacman imports
from pacman.model.constraints.placer_constraints.placer_board_constraint \
    import PlacerBoardConstraint

# front end common imports
from pacman.model.resources.iptag_resource import IPtagResource
from pacman.model.resources.resource_container import ResourceContainer
from spinn_front_end_common.interface.buffer_management.buffer_models\
    .abstract_receive_buffers_to_host import AbstractReceiveBuffersToHost
from spinn_front_end_common.interface.buffer_management.storage_objects\
    .end_buffering_state import EndBufferingState
from spinn_front_end_common.utilities import exceptions

# general imports
import sys
import math


class ReceiveBuffersToHostBasicImpl(AbstractReceiveBuffersToHost):
    """ This class stores the information required to activate the buffering \
        output functionality for a vertex
    """

    def __init__(self):
        """
        :return: None
        :rtype: None
        """
        self._buffering_output = False
        self._buffering_ip_address = None
        self._buffering_port = None
        self._minimum_sdram_for_buffering = 0
        self._buffered_sdram_per_timestep = 0
        self._buffered_regions = list()
        self._buffered_state_region = None

    def buffering_output(self):
        """ True if the output buffering mechanism is activated

        :return: Boolean indicating whether the output buffering mechanism\
                is activated
        :rtype: bool
        """
        return self._buffering_output

    def activate_buffering_output(
            self, buffering_ip_address=None, buffering_port=None,
            board_address=None, minimum_sdram_for_buffering=0,
            buffered_sdram_per_timestep=0):
        """ Activates the output buffering mechanism

        :param buffering_ip_address: IP address of the host which supports\
                the buffering output functionality
        :type buffering_ip_address: string
        :param buffering_port: UDP port of the host which supports\
                the buffering output functionality
        :type buffering_port: int

        :return: None
        :rtype: None
        """
        if (not self._buffering_output and buffering_ip_address is not None and
                buffering_port is not None):
            self._buffering_output = True

            # add placement constraint if needed
            if board_address is not None:
                self.add_constraint(PlacerBoardConstraint(board_address))
            self._buffering_ip_address = buffering_ip_address
            self._buffering_port = buffering_port
        self._minimum_sdram_for_buffering = minimum_sdram_for_buffering
        self._buffered_sdram_per_timestep = buffered_sdram_per_timestep

    def get_extra_resources(self, buffering_ip_address, buffering_port,
                            notification_tag=None):
        """ Get any additional resource required

        :param buffering_ip_address: IP address of the host which supports\
                the buffering output functionality
        :param buffering_port: UDP port of the host which supports\
                the buffering output functionality
        :param notification_tag: ??????????????
        :return: a resource container
        """
        if (not self._buffering_output and buffering_ip_address is not None and
                buffering_port is not None):

            # create new resources to handle a new tag
            return ResourceContainer(iptags=[
                IPtagResource(buffering_ip_address, buffering_port,
                              True, notification_tag)])
        return ResourceContainer()

    @staticmethod
    def get_buffer_state_region_size(n_buffered_regions):
        """ Get the size of the buffer state region for the given number of\
            buffered regions
        """
        return EndBufferingState.size_of_region(n_buffered_regions)

    @staticmethod
    def get_recording_data_size(n_buffered_regions):
        """ Get the size of the recording data for the given number of\
            buffered regions
        """
        return 12 + (n_buffered_regions * 4)

    def reserve_buffer_regions(
            self, spec, state_region, buffer_regions, region_sizes):
        """ Reserves the region for recording and the region for storing the\
            end state of the buffering

        :param spec: The data specification to reserve the region in
        :param state_region: The id of the region to use as the end state\
                region
        :param buffer_regions: The regions ids to reserve for buffering
        :param region_sizes: The sizes of the regions to reserve
        """
        if len(buffer_regions) != len(region_sizes):
            raise exceptions.ConfigurationException(
                "The number of buffer regions must match the number of"
                " regions sizes")
        for (buffer_region, region_size) in zip(
                buffer_regions, region_sizes):
            if region_size > 0:
                self._buffered_regions.append(buffer_region)
                spec.reserve_memory_region(
                    region=buffer_region, size=region_size,
                    label="RECORDING_REGION_{}".format(buffer_region),
                    empty=True)
        spec.reserve_memory_region(
            region=state_region,
            size=EndBufferingState.size_of_region(len(buffer_regions)),
            label='BUFFERED_OUT_STATE', empty=True)
        self._buffered_state_region = state_region

    def get_tag(self, ip_tags):
        """ Finds the tag for buffering from the set of tags presented

        :param ip_tags: A list of ip tags in which to find the tag
        """
        for tag in ip_tags:
            if (tag.ip_address == self._buffering_ip_address and
                    tag.port == self._buffering_port):
                return tag
        return None

    def write_recording_data(
            self, spec, ip_tags, region_sizes, buffer_size_before_receive,
            time_between_requests=0):
        """ Writes the recording data to the data specification

        :param spec: The data specification to write to
        :param ip_tags: The list of tags assigned to the vertex
        :param region_sizes: An ordered list of the sizes of the regions in\
                which buffered recording will take place
        :param buffer_size_before_receive: The amount of data that can be\
                stored in the buffer before a message is sent requesting the\
                data be read
        :param time_between_requests: The amount of time between requests for\
                more data
        """
        if self._buffering_output:

            # If buffering is enabled, write the tag for buffering
            ip_tag = self.get_tag(ip_tags)
            if ip_tag is None:
                raise Exception(
                    "No tag for output buffering was assigned to this vertex")
            spec.write_value(data=ip_tag.tag)
        else:
            spec.write_value(data=0)
        spec.write_value(data=buffer_size_before_receive)
        spec.write_value(data=time_between_requests)
        for region_size in region_sizes:
            spec.write_value(data=region_size)

    def get_minimum_buffer_sdram_usage(self):
        return self._minimum_sdram_for_buffering

    def get_n_timesteps_in_buffer_space(self, buffer_space):
        if self._buffered_sdram_per_timestep == 0:
            return sys.maxint
        return int(math.floor(
            buffer_space / self._buffered_sdram_per_timestep))

    def get_buffered_regions(self):
        return self._buffered_regions

    def get_buffered_state_region(self):
        return self._buffered_state_region
