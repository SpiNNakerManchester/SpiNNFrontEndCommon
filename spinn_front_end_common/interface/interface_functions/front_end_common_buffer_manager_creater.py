from pacman.utilities.utility_objs.progress_bar import ProgressBar
from spinn_front_end_common.interface.buffer_management.buffer_manager import \
    BufferManager
from spinn_front_end_common.interface.buffer_management.\
    buffer_models.abstract_sends_buffers_from_host_partitioned_vertex import \
    AbstractSendsBuffersFromHostPartitionedVertex


class FrontEndCommonBufferManagerCreater(object):
    """
    """

    def __call__(
            self, placements, tags, txrx, reports_states, app_data_folder):
        """
        :param placements: the placements object
        :param tags: the tags object
        :return: None
        """
        progress_bar = ProgressBar(
            len(list(placements.placements)), "Initialising buffers")

        # Create the buffer manager
        send_buffer_manager = BufferManager(
            placements, tags, txrx, reports_states, app_data_folder)

        for placement in placements.placements:
            if isinstance(placement.subvertex,
                          AbstractSendsBuffersFromHostPartitionedVertex):

                # Add the vertex to the managed vertices
                send_buffer_manager.add_sender_vertex(placement.subvertex)
            progress_bar.update()
        progress_bar.end()

        return {"buffer_manager": send_buffer_manager}
