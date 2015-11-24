from pacman.utilities.utility_objs.progress_bar import ProgressBar
from spinn_front_end_common.interface.buffer_management.buffer_manager import \
    BufferManager
from spinn_front_end_common.interface.buffer_management.\
    buffer_models.abstract_sends_buffers_from_host_partitioned_vertex import \
    AbstractSendsBuffersFromHostPartitionedVertex
from spinn_front_end_common.interface.buffer_management.buffer_models\
    .abstract_receive_buffers_to_host \
    import AbstractReceiveBuffersToHost


class FrontEndCommonBufferManagerCreater(object):
    """
    """

    def __call__(
            self, placements, tags, txrx, reports_states, graph_mapper,
            app_data_folder):
        """
        :param placements: the placements object
        :param tags: the tags object
        :return: None
        """
        progress_bar = ProgressBar(
            len(list(placements.placements)), "Initialising buffers")

        # Create the buffer manager
        buffer_manager = BufferManager(
            placements, tags, txrx, reports_states, app_data_folder)

        for placement in placements.placements:
            if isinstance(placement.subvertex,
                          AbstractSendsBuffersFromHostPartitionedVertex):

                # Add the vertex to the managed vertices
                buffer_manager.add_sender_vertex(placement.subvertex)

            # graph_mapper could be None if there is no partitionable_graph
            if graph_mapper is not None:
                vertex = graph_mapper.get_vertex_from_subvertex(
                    placement.subvertex)
                if isinstance(vertex, AbstractReceiveBuffersToHost):
                    if vertex.buffering_output:
                        buffer_manager.add_receiving_vertex(
                            placement.subvertex)
                        vertex.buffer_manager = buffer_manager

            # Partitioned vertices can also be output buffered
            if isinstance(placement.subvertex, AbstractReceiveBuffersToHost):
                if placement.subvertex.buffering_output:
                    buffer_manager.add_receiving_vertex(placement.subvertex)
                    placement.subvertex.buffer_manager = buffer_manager
            progress_bar.update()
        progress_bar.end()

        return {"buffer_manager": buffer_manager}
