"""
FrontEndCommonBufferManagerCreater
"""

from pacman.utilities.utility_objs.progress_bar import ProgressBar
from spinn_front_end_common.interface.buffer_management.buffer_manager import \
    BufferManager
from spinn_front_end_common.interface.buffer_management.\
    buffer_models.abstract_sends_buffers_from_host_partitioned_vertex import \
    AbstractSendsBuffersFromHostPartitionedVertex


class FrontEndCommonBufferManagerCreater(object):
    """
    FrontEndCommonBufferManagerCreater
    """

    def __call__(
            self, partitioned_graph, placements, tags, txrx, reports_states,
            app_data_folder):
        """
        interface for buffered vertices
        :param partitioned_graph: the partitioned graph object
        :param placements: the placements object
        :param tags: the tags object
        :return: None
        """
        progress_bar = ProgressBar(
            len(partitioned_graph.subvertices), "Initialising buffers")

        # Create the buffer manager
        send_buffer_manager = BufferManager(
            placements, tags, txrx, reports_states, app_data_folder)

        for partitioned_vertex in partitioned_graph.subvertices:
            if isinstance(partitioned_vertex,
                          AbstractSendsBuffersFromHostPartitionedVertex):

                # Add the vertex to the managed vertices
                send_buffer_manager.add_sender_vertex(partitioned_vertex)
            progress_bar.update()
        progress_bar.end()

        return {"buffer_manager": send_buffer_manager}

