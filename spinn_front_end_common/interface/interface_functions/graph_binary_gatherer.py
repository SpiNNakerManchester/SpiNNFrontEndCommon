from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.utilities.utility_objs import ExecutableTargets
from spinn_front_end_common.utilities.exceptions import (
    ExecutableNotFoundException)
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary


class GraphBinaryGatherer(object):
    """ Extracts binaries to be executed.
    """

    __slots__ = ["_exe_finder", "_exe_targets"]

    def __init__(self):
        self._exe_finder = None
        self._exe_targets = None

    def __call__(
            self, placements, graph, executable_finder, graph_mapper=None):
        self._exe_finder = executable_finder
        self._exe_targets = ExecutableTargets()
        progress = ProgressBar(graph.n_vertices, "Finding binaries")
        for vertex in progress.over(graph.vertices):
            placement = placements.get_placement_of_vertex(vertex)
            self.__get_binary(placement, vertex)
            if graph_mapper is not None:
                self.__get_binary(placement,
                                  graph_mapper.get_application_vertex(vertex))

        return self._exe_targets

    def __get_binary(self, placement, vertex):
        # If we've got junk input (shouldn't happen), ignore it
        if vertex is None:
            return
        # if the vertex cannot generate a DSG, ignore it
        if not isinstance(vertex, AbstractHasAssociatedBinary):
            return

        # Get name of binary from vertex
        binary_name = vertex.get_binary_file_name()
        exec_type = vertex.get_binary_start_type()

        # Attempt to find this within search paths
        binary_path = self._exe_finder.get_executable_path(binary_name)
        if binary_path is None:
            raise ExecutableNotFoundException(binary_name)

        self._exe_targets.add_processor(
            binary_path, placement.x, placement.y, placement.p, exec_type)
