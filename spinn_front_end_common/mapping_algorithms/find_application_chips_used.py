from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinn_front_end_common.utilities.utility_objs import ExecutableType


class FindApplicationChipsUsed(object):

    def __call__(self, placements, graph_mapper=None):
        chips_used = set()
        for placement in placements:
            # find binary type if applicable
            binary_start_type = None
            has_binary = isinstance(
                placement.vertex, AbstractHasAssociatedBinary)

            if not has_binary and graph_mapper is not None:
                app_vertex = graph_mapper.get_application_vertex(
                    placement.vertex)
                if isinstance(app_vertex, AbstractHasAssociatedBinary):
                    binary_start_type = app_vertex.get_binary_start_type()
            else:
                binary_start_type = placement.vertex.get_binary_start_type()

            if binary_start_type != ExecutableType.SYSTEM:
                chips_used.add((placement.x, placement.y))
        return len(chips_used)
