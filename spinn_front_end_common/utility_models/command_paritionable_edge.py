from spinn_front_end_common.utility_models.command_partitioned_edge \
    import CommandPartitionedEdge
from pacman.model.partitionable_graph.multi_cast_partitionable_edge \
    import MultiCastPartitionableEdge


class CommandPartitionableEdge(MultiCastPartitionableEdge):
    """ An edge from a command sender to a partitionable vertex whose\
        sub-vertices are to receive those commands
    """

    def __init__(self, pre_vertex, post_vertex, commands):
        MultiCastPartitionableEdge.__init__(self, pre_vertex, post_vertex)
        self._commands = commands
        self._partitioned_edges = list()

    def create_subedge(self, pre_subvertex, pre_subvertex_slice,
                       post_subvertex, post_subvertex_slice, label=None,
                       constraints=None):
        subedge = CommandPartitionedEdge(pre_subvertex, post_subvertex,
                                         self._commands)
        self._partitioned_edges.append(subedge)
        return subedge

    @property
    def partitioned_edges(self):
        return self._partitioned_edges
