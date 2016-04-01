
# pacman imports
from pacman.model.constraints.abstract_constraints.\
    abstract_placer_constraint import \
    AbstractPlacerConstraint
from pacman.model.constraints.placer_constraints.\
    placer_chip_and_core_constraint \
    import PlacerChipAndCoreConstraint
from pacman.utilities import utility_calls
from spinn_machine.utilities.progress_bar import ProgressBar
from pacman.utilities.utility_objs.resource_tracker import ResourceTracker

# general imports
import logging
logger = logging.getLogger(__name__)


class FrontEndCommonPartitionedGraphMeasurer(object):
    """ Works out how many chips a partitioned graph needs
    """

    def __call__(self, partitioned_graph, machine):
        """

        :param partitioned_graph: The partitioned_graph to measure
        :type partitioned_graph:\
                    :py:class:`pacman.model.partitioned_graph.partitioned_graph.PartitionedGraph`
        :return: The size of the graph in number of chips
        :rtype: int
        """

        # check that the algorithm can handle the constraints
        utility_calls.check_algorithm_can_support_constraints(
            constrained_vertices=partitioned_graph.subvertices,
            supported_constraints=[PlacerChipAndCoreConstraint],
            abstract_constraint_type=AbstractPlacerConstraint)

        ordered_subverts = utility_calls.sort_objects_by_constraint_authority(
            partitioned_graph.subvertices)

        # Iterate over subvertices and allocate
        progress_bar = ProgressBar(len(ordered_subverts),
                                   "Measuring the partitioned graph")
        resource_tracker = ResourceTracker(machine)
        for subvertex in ordered_subverts:
            resource_tracker.allocate_constrained_resources(
                subvertex.resources_required, subvertex.constraints)
            progress_bar.update()
        progress_bar.end()
        return {'n_chips': len(resource_tracker.keys)}
