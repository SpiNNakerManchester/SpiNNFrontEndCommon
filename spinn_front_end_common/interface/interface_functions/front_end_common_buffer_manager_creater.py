from pacman.utilities.utility_objs.progress_bar import ProgressBar
from spinn_front_end_common.interface.buffer_management.buffer_manager import \
    BufferManager
from spinn_front_end_common.interface.buffer_management.\
    buffer_models.abstract_sends_buffers_from_host_partitioned_vertex import \
    AbstractSendsBuffersFromHostPartitionedVertex
from spinn_front_end_common.interface.buffer_management.buffer_models\
    .receive_buffers_to_host_partitionable_vertex \
    import ReceiveBuffersToHostPartitionableVertex


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

            # On reload, graph_mapper is None, and buffered out is no longer
            # useful
            if graph_mapper is not None:
                vertex = graph_mapper.get_vertex_from_subvertex(
                    placement.subvertex)
                if isinstance(vertex, ReceiveBuffersToHostPartitionableVertex):
                    list_of_regions = vertex.get_buffered_regions_list()
                    buffer_manager.add_receiving_vertex(
                        placement.subvertex, list_of_regions)
                    vertex.buffer_manager = buffer_manager
            progress_bar.update()
        progress_bar.end()

        return {"buffer_manager": buffer_manager}
