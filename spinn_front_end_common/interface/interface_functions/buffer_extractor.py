import logging
from spinn_utilities.log import FormatAdapter
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.interface.buffer_management.buffer_models \
    import (
        AbstractReceiveBuffersToHost)

logger = FormatAdapter(logging.getLogger(__name__))


class BufferExtractor(object):
    """ Extracts data in between runs
    """

    __slots__ = []

    def __call__(self, machine_graph, placements, buffer_manager):

        # Count the regions to be read
        n_regions_to_read, recording_placements = self._count_regions(
            machine_graph, placements)
        if not n_regions_to_read:
            logger.info("No recorded data to extract")
            return

        # Read back the regions
        progress = ProgressBar(
            n_regions_to_read, "Extracting buffers from the last run")
        try:
            buffer_manager.get_data_for_placements(
                recording_placements, progress)
        finally:
            progress.end()

    @staticmethod
    def _count_regions(machine_graph, placements):
        # Count the regions to be read
        n_regions_to_read = 0
        recording_placements = list()
        for vertex in machine_graph.vertices:
            if isinstance(vertex, AbstractReceiveBuffersToHost):
                n_regions_to_read += len(vertex.get_recorded_region_ids())
                placement = placements.get_placement_of_vertex(vertex)
                recording_placements.append(placement)
        return n_regions_to_read, recording_placements
