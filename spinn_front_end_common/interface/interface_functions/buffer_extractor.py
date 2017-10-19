from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.interface.buffer_management.buffer_models \
    import AbstractReceiveBuffersToHost
from spinn_utilities.progress_bar import ProgressBar


class BufferExtractor(object):
    """ Extracts data in between runs
    """

    __slots__ = []

    def __call__(self, machine_graph, placements, buffer_manager, ran_token):
        if not ran_token:
            raise ConfigurationException("The ran token has not been set")

        # Count the regions to be read
        n_regions_to_read = 0
        vertices = list()
        for vertex in machine_graph.vertices:
            if isinstance(vertex, AbstractReceiveBuffersToHost):
                n_regions_to_read += len(vertex.get_recorded_region_ids())
                vertices.append(vertex)

        progress = ProgressBar(
            n_regions_to_read, "Extracting buffers from the last run")

        # Read back the regions
        for vertex in vertices:
            placement = placements.get_placement_of_vertex(vertex)
            for recording_region_id in vertex.get_recorded_region_ids():
                buffer_manager.get_data_for_vertex(
                    placement, recording_region_id)
                progress.update()
        progress.end()
