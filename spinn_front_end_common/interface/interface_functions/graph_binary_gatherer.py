from spinn_utilities.progress_bar import ProgressBar

from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinnman.model import ExecutableTargets


class GraphBinaryGatherer(object):
    """ Extracts binaries to be executed
    """

    __slots__ = []

    def __call__(
            self, placements, graph, executable_finder, graph_mapper=None):
        executable_targets = ExecutableTargets()
        progress = ProgressBar(graph.n_vertices, "Finding binaries")
        for vertex in progress.over(graph.vertices):
            placement = placements.get_placement_of_vertex(vertex)
            self._get_binary(
                placement, vertex, executable_targets, executable_finder)

            if graph_mapper is not None:
                associated_vertex = graph_mapper.get_application_vertex(vertex)
                self._get_binary(
                    placement, associated_vertex, executable_targets,
                    executable_finder)

        return executable_targets

    @staticmethod
    def _get_binary(
            placement, associated_vertex, executable_targets,
            executable_finder):
        # if the vertex cannot generate a DSG, ignore it
        if not isinstance(associated_vertex, AbstractHasAssociatedBinary):
            return None

        # Get name of binary from vertex
        binary_name = associated_vertex.get_binary_file_name()

        # Attempt to find this within search paths
        binary_path = executable_finder.get_executable_path(binary_name)
        if binary_path is None:
            raise exceptions.ExecutableNotFoundException(binary_name)

        executable_targets.add_processor(
            binary_path, placement.x, placement.y, placement.p)
