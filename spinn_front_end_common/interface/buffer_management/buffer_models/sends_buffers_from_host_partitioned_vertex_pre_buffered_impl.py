"""
SendsBuffersFromHostPartitionedVertexPreBufferedImpl
"""

# spinn front end common imports
from spinn_front_end_common.interface.buffer_management.buffer_models.\
    abstract_sends_buffers_from_host_partitioned_vertex \
    import AbstractSendsBuffersFromHostPartitionedVertex

# general imports
import logging

logger = logging.getLogger(__name__)


class SendsBuffersFromHostPartitionedVertexPreBufferedImpl(
        AbstractSendsBuffersFromHostPartitionedVertex):
    """ Implementation of the AbstractSendsBuffersFromHostPartitionedVertex\
        which uses an existing set of buffers for the details
    """

    def __init__(self, send_buffers):
        """

        :param send_buffers: A dictionary of the buffers of spikes to send,
                    indexed by the regions
        :type send_buffers: dict(int -> \
                    :py:class:`spinnaker.pyNN.buffer_management.storage_objects.buffered_sending_region.BufferedSendingRegion`)
        """
        self._send_buffers = send_buffers

    def get_regions(self):
        """
        returns the regions which has buffers to send
        :return:
        """
        return self._send_buffers.keys()

    def get_max_buffer_size_possible(self, region):
        """
        returns the max_possible size of a buffered region
        :param region: the region to find the max possible size of
        :return: the max possible size of the buffered region
        """
        return self._send_buffers[region].max_buffer_size_possible

    def get_region_buffer_size(self, region):
        """
        returns the size of a given regions buffer
        :param region: the region to find the size of
        :return: the size of the buffer
        """
        return self._send_buffers[region].buffer_size

    def is_next_timestamp(self, region):
        """
        checks if there is more timestamps whcih need transmitting
        :param region: the region to check
        :return: boolean
        """
        return self._send_buffers[region].is_next_timestamp

    def get_next_timestamp(self, region):
        """
        returns the next time stamp avilable in the buffered region
        :param region: the region id which is being asked
        :return: the next time stamp
        """
        return self._send_buffers[region].next_timestamp

    def is_next_key(self, region, timestamp):
        """
        checks if there is more keys to transmit for a given region in a given
         timestamp
        :param region: the region id to check
        :param timestamp:  the timestamp to check
        :return: bool
        """
        return self._send_buffers[region].is_next_key(timestamp)

    def get_next_key(self, region):
        """
        gets the next key for a given region
        :param region: the region to get the next key from
        :return:
        """
        return self._send_buffers[region].next_key

    def is_empty(self, region):
        """
        helper method to check if a region is empty
        :param region: the region id to check
        :return: bool
        """
        return len(self._send_buffers[region].timestamps) == 0
