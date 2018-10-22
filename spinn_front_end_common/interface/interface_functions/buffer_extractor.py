from spinn_front_end_common.interface.buffer_management.buffer_models \
    import AbstractReceiveBuffersToHost
from spinn_utilities.progress_bar import ProgressBar


class BufferExtractor(object):
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
            readPlacements = list()
            for placement in placements:
                if placement.vertex in vertices:
                    print(placement)
                    print(placement.vertex.get_recorded_region_ids())
                    print(placement.vertex.get_recording_region_base_address(buffer_manager._transceiver, placement))
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
