from spinn_machine.utilities.progress_bar import ProgressBar

from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.abstract_models.abstract_has_associated_binary\
    import AbstractHasAssociatedBinary
from spinnman.model.executable_targets import ExecutableTargets


class FrontEndCommonGraphBinaryGatherer(object):
    """ Extracts binaries to be executed
    """

    __slots__ = []

    def __call__(
            self, placements, graph, executable_finder, graph_mapper=None):

        executable_targets = ExecutableTargets()
        binary_start_type = None
        progress_bar = ProgressBar(graph.n_vertices, "Finding binaries")
        for vertex in graph.vertices:
            placement = placements.get_placement_of_vertex(vertex)
            placement_binary_start_type = self._get_binary(
                placement, vertex, executable_targets, executable_finder)

            if (placement_binary_start_type is None and
                    graph_mapper is not None):
                associated_vertex = graph_mapper.get_application_vertex(vertex)
                placement_binary_start_type = self._get_binary(
                    placement, associated_vertex, executable_targets,
                    executable_finder)

            if (placement_binary_start_type is not None and
                    binary_start_type is not None and
                    placement_binary_start_type != binary_start_type):
                raise exceptions.ConfigurationException(
                    "All binaries must be of the same start type - existing"
                    " binaries have start type {} but placement {} has start"
                    " type {}".format(
                        binary_start_type, placement,
                        placement_binary_start_type))
            binary_start_type = placement_binary_start_type
            progress_bar.update()
        progress_bar.end()

        return executable_targets, binary_start_type

    def _get_binary(
            self, placement, associated_vertex, executable_targets,
            executable_finder):

        # if the vertex can generate a DSG, call it
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
        return associated_vertex.get_binary_start_type()
