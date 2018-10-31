from collections import OrderedDict
import json

from spinn_front_end_common.interface.buffer_management.buffer_models \
    import AbstractReceiveBuffersToHost
from spinn_utilities.progress_bar import ProgressBar


class PlacementsToJson(object):
    """ Extracts data in between runs
    """

    __slots__ = []

    def __call__(self, machine_graph, placements, transceiver, file_path):

        # Count the regions to be read
        n_regions_to_read, vertices = self._count_regions(machine_graph)

        # Read back the regions
        progress = ProgressBar(
            n_regions_to_read, "Extracting placements")
        json_obj = list()
        for placement in placements:
            if placement.vertex in vertices:
                json_placement = OrderedDict()
                json_placement["x"] = placement.x
                json_placement["y"] = placement.y
                json_placement["p"] = placement.p
                vertex = placement.vertex
                json_vertex = OrderedDict()
                json_vertex["label"] = vertex.label
                json_vertex["recordedRegionIds"] = vertex.get_recorded_region_ids()
                json_vertex["recordingRegionBaseAddress"] = vertex.get_recording_region_base_address(transceiver, placement)
                json_placement["vertex"] = json_vertex
                json_obj.append(json_placement)

        # dump to json file
        with open(file_path, "w") as f:
            json.dump(json_obj, f)

            progress.end()

        return file_path

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
