# front end common imports
from spinn_front_end_common.interface.buffer_management.buffer_models.\
    sends_buffers_from_host_pre_buffered_impl import \
    SendsBuffersFromHostPreBufferedImpl
from spinn_front_end_common.interface.buffer_management.storage_objects.\
    buffered_sending_region import BufferedSendingRegion
from spinn_front_end_common.utilities import constants

_MAX_MEMORY_USAGE = constants.MAX_SIZE_OF_BUFFERED_REGION_ON_CHIP


class ReloadBufferedVertex(SendsBuffersFromHostPreBufferedImpl):
    """ A Buffered sending vertex when using reload
    """

    def __init__(self, label, region_files_tuples):
        """
        :param label: The label of the vertex
        :param region_files_tuples: A dictionary of region id -> file name
        """
        self._label = label

        self._send_buffers = dict()
        for (region_id, filename, max_size_of_buffer) in region_files_tuples:
            send_buffer = BufferedSendingRegion(max_size_of_buffer)
            with open(filename, "r") as reader:
                line = reader.readline()
                while line != "":
                    bits = line.split(":")
                    send_buffer.add_key(int(bits[0]), int(bits[1]))
                    line = reader.readline()
            self._send_buffers[region_id] = send_buffer

    @property
    def send_buffers(self):
        return self._send_buffers

    @send_buffers.setter
    def send_buffers(self, value):
        self._send_buffers = value
