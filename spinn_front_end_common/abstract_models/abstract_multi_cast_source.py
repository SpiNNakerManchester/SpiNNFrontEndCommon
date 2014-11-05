from abc import ABCMeta
from six import add_metaclass

from pacman.model.partitionable_graph.abstract_partitionable_vertex \
    import AbstractPartitionableVertex
from spinn_front_end_common.abstract_models.abstract_data_specable_vertex \
    import AbstractDataSpecableVertex


@add_metaclass(ABCMeta)
class AbstractMultiCastSource(AbstractDataSpecableVertex,
                              AbstractPartitionableVertex):

    def __init__(self, machine_time_step):
        """
        constructor that depends upon the Component vertex
        """
        AbstractDataSpecableVertex.__init__(
            self, label="multi_cast_source_sender",
            machine_time_step=machine_time_step)
        AbstractPartitionableVertex.__init__(
            self, label="multi_cast_source_sender", n_atoms=1,
            max_atoms_per_core=1)