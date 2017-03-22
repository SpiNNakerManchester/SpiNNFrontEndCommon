
# pacman imports
from spinn_machine.utilities.progress_bar import ProgressBar
from pacman.utilities.utility_objs.resource_tracker import ResourceTracker
from pacman.utilities.algorithm_utilities import placer_algorithm_utilities

# general imports
import logging
logger = logging.getLogger(__name__)


class FrontEndCommonGraphMeasurer(object):
    """ Works out how many chips a machine graph needs
    """

    __slots__ = []

    def __call__(self, machine_graph, machine):
        """

        :param machine_graph: The machine_graph to measure
        :type machine_graph:\
                    :py:class:`pacman.model.graph.machine.machine_graph.MachineGraph`
        :return: The size of the graph in number of chips
        :rtype: int
        """

        # check that the algorithm can handle the constraints
        ResourceTracker.check_constraints(machine_graph.vertices)

        ordered_vertices = \
            placer_algorithm_utilities.sort_vertices_by_known_constraints(
                machine_graph.vertices)

        # Iterate over vertices and allocate
        progress_bar = ProgressBar(
            machine_graph.n_vertices, "Measuring the graph")
        resource_tracker = ResourceTracker(machine)
        for vertex in ordered_vertices:
            resource_tracker.allocate_constrained_resources(
                vertex.resources_required, vertex.constraints)
            progress_bar.update()
        progress_bar.end()
        return len(resource_tracker.keys)
