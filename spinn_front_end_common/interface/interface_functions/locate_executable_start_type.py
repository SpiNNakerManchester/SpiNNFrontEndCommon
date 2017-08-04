from spinn_front_end_common.abstract_models.\
    abstract_has_associated_binary import AbstractHasAssociatedBinary
from spinn_front_end_common.utilities.utility_objs.executable_start_type \
    import ExecutableStartType
from spinn_front_end_common.utilities import exceptions
from spinn_utilities.progress_bar import ProgressBar


class LocateExecutableStartType(object):

    def __call__(self, graph, graph_mapper=None):

        progress = ProgressBar(
            graph.n_vertices, "Finding executable_start_types")
        binary_start_type = None
        if len(graph.vertices) == 0:
            return ExecutableStartType.NO_APPLICATION
        for vertex in progress.over(graph.vertices):

            placement_binary_start_type = None

            if isinstance(vertex, AbstractHasAssociatedBinary):
                placement_binary_start_type = vertex.get_binary_start_type()
            elif graph_mapper is not None:
                associated_vertex = graph_mapper.get_application_vertex(vertex)
                if isinstance(associated_vertex, AbstractHasAssociatedBinary):
                    placement_binary_start_type = \
                        associated_vertex.get_binary_start_type()

            if binary_start_type is None:
                binary_start_type = placement_binary_start_type

            # check all vertices have the same start type
            if (placement_binary_start_type is not None and
                    binary_start_type is not None and
                    placement_binary_start_type != binary_start_type):
                raise exceptions.ConfigurationException(
                    "All binaries must be of the same start type -"
                    " existing binaries have start type {} but "
                    "vertex {} has start type {}".format(
                        binary_start_type, vertex.label,
                        placement_binary_start_type))
        return binary_start_type
