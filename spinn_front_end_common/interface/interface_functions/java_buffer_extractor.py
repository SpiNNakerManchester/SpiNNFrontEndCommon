from spinn_front_end_common.interface.buffer_management.buffer_models \
    import AbstractReceiveBuffersToHost
from spinn_utilities.progress_bar import ProgressBar


class JavaBufferExtractor(object):
    """ Extracts data in between runs
    """

    __slots__ = []

    def __call__(self, machine_graph, placements, buffer_manager):

        # Count the regions to be read
        n_regions_to_read, vertices = self._count_regions(machine_graph)

        # Read back the regions
        progress = ProgressBar(
            n_regions_to_read, "Extracting buffers from the last run")
        try:
            buffer_manager.get_data_for_vertices(vertices, progress)
        finally:
            progress.end()

    @staticmethod
    def _count_regions(machine_graph):
        # Count the regions to be read
        n_regions_to_read = 0
        vertices = list()
        for vertex in machine_graph.vertices:
            if isinstance(vertex, AbstractReceiveBuffersToHost):
                n_regions_to_read += len(vertex.get_recorded_region_ids())
                vertices.append(vertex)
        return n_regions_to_read, vertices
