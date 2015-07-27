"""
ReloadBufferedVertex
"""

# front end common imports
from spinn_front_end_common.interface.buffer_management.buffer_models.\
    sends_buffers_from_host_partitioned_vertex_pre_buffered_impl import \
    SendsBuffersFromHostPartitionedVertexPreBufferedImpl
from spinn_front_end_common.interface.buffer_management.storage_objects.\
    buffered_sending_region import BufferedSendingRegion

# general imports
import os


class ReloadBufferedVertex(
        SendsBuffersFromHostPartitionedVertexPreBufferedImpl):
    """
    A class to work for buffered stuff for relaod purposes
    """

    def __init__(self, buffered_region_file_paths, label):
        self._label = label
        self._send_buffers = \
            self._read_in_send_buffers_from_folder(buffered_region_file_paths)
        SendsBuffersFromHostPartitionedVertexPreBufferedImpl.__init__(
            self, self._send_buffers)

    def _read_in_send_buffers_from_folder(self, base_folder):
        """ with a base folder, searches for its own buffered regions and
        reads them in to buffered sneding regions

        :param base_folder: the folder which contains its buffered regions
        :return: the send buffers as a dict of region id and bufferedSendRegion
        """
        files_in_folder = os.listdir(base_folder)
        send_buffers = dict()
        for possible_buffer_file in files_in_folder:
            # search for files which are associated with this vertex
            search_for_name = "buffered_sending_region_{}".format(self._label)
            if search_for_name in os.path.basename(possible_buffer_file):
                bits = os.path.basename(possible_buffer_file).split("_")
                # last bit of the bits should be the region id so, locate
                region_id = int(bits[len(bits) - 1])
                send_buffers[region_id] = BufferedSendingRegion()
                reader = open(possible_buffer_file, "r")
                line = reader.readline()
                while line != "":
                    bits = line.split(":")
                    send_buffers[region_id].add_key(int(bits[0]), int(bits[1]))
                    line = reader.readline()
        return send_buffers
