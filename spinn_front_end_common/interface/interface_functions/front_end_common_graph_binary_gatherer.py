from spinn_machine.utilities.progress_bar import ProgressBar

from spinn_front_end_common.abstract_models.abstract_has_associated_binary\
    import AbstractHasAssociatedBinary
from spinn_front_end_common.utilities.utility_objs.executable_targets import \
    ExecutableTargets
from spinn_front_end_common.utilities import exceptions


class FrontEndCommonGraphBinaryGatherer(object):
    """ Extracts binaries to be executed
    """

    __slots__ = []

    def __call__(
            self, placements, graph, executable_finder, graph_mapper=None):

        executable_targets = ExecutableTargets()
        progress_bar = ProgressBar(
            len(list(graph.vertices)), "Finding binaries")
        for vertex in graph.vertices:
            placement = placements.get_placement_of_vertex(vertex)
            if (not self._get_binary(
                placement, vertex, executable_targets, executable_finder) and
                    graph_mapper is not None):
                associated_vertex = graph_mapper.get_application_vertex(vertex)
                self._get_binary(
                    placement, associated_vertex, executable_targets,
                    executable_finder)
            progress_bar.update()
        progress_bar.end()

        return executable_targets

    def _get_binary(
            self, placement, associated_vertex, executable_targets,
            executable_finder):

        # if the vertex can generate a DSG, call it
        if isinstance(associated_vertex, AbstractHasAssociatedBinary):

            # Get name of binary from vertex
            binary_name = associated_vertex.get_binary_file_name()

            # Attempt to find this within search paths
            binary_path = executable_finder.get_executable_path(binary_name)
            if binary_path is None:
                raise exceptions.ExecutableNotFoundException(binary_name)

            if not executable_targets.has_binary(binary_path):
                executable_targets.add_binary(binary_path)
            executable_targets.add_processor(
                binary_path, placement.x, placement.y, placement.p)
            return True
        return False
