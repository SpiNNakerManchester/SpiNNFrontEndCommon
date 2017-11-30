from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from pacman.model.graphs.machine import MachineVertex
from spinn_machine import CoreSubsets
from spinn_utilities.progress_bar import ProgressBar


class LocateExecutableStartType(object):
    def __call__(self, graph, placements, graph_mapper=None):
        if len(graph.vertices) == 0:
            return [ExecutableType.NO_APPLICATION]

        binary_start_types = dict()
        progress = ProgressBar(
            graph.n_vertices, "Finding executable_start_types")
        for vertex in progress.over(graph.vertices):
            # try to locate binary type, but possible it doesn't have one
            placement_binary_start_type = None
            if isinstance(vertex, AbstractHasAssociatedBinary):
                placement_binary_start_type = vertex.get_binary_start_type()
            elif graph_mapper is not None:
                associated_vertex = graph_mapper.get_application_vertex(vertex)
                if isinstance(associated_vertex, AbstractHasAssociatedBinary):
                    placement_binary_start_type = \
                        associated_vertex.get_binary_start_type()

            # check for vertices with no associated binary, if so, ignore
            if placement_binary_start_type is not None:
                # update core subset with location of the vertex on the machine
                if placement_binary_start_type not in binary_start_types:
                    binary_start_types[placement_binary_start_type] = \
                        CoreSubsets()

                if isinstance(vertex, MachineVertex):
                    self._sort_out_machine_vertex(
                        vertex, placements,
                        binary_start_types[placement_binary_start_type])
                elif graph_mapper is not None:
                    machine_verts = graph_mapper.get_machine_vertices(vertex)
                    for machine_vertex in machine_verts:
                        self._sort_out_machine_vertex(
                            machine_vertex, placements,
                            binary_start_types[placement_binary_start_type])

        # only got apps with no binary, such as external devices. return no app
        if len(binary_start_types) == 0:
            return [ExecutableType.NO_APPLICATION]

        return binary_start_types

    @staticmethod
    def _sort_out_machine_vertex(machine_vertex, placements, core_subsets):
        placement = placements.get_placement_of_vertex(machine_vertex)
        core_subsets.add_processor(x=placement.x, y=placement.y,
                                   processor_id=placement.p)
