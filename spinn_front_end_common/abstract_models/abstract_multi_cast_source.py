from pacman.model.partitionable_graph.abstract_partitionable_vertex \
    import AbstractPartitionableVertex
from spinn_front_end_common.abstract_models.abstract_data_specable_vertex \
    import AbstractDataSpecableVertex

from abc import ABCMeta
from six import add_metaclass
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractMultiCastSource(AbstractDataSpecableVertex,
                              AbstractPartitionableVertex):

    def __init__(self, machine_time_step, timescale_factor):
        """
        constructor that depends upon the Component vertex
        """
        AbstractDataSpecableVertex.__init__(
            self, n_atoms=1, label="multi_cast_source_sender",
            machine_time_step=machine_time_step,
            timescale_factor=timescale_factor)
        AbstractPartitionableVertex.__init__(
            self, label="multi_cast_source_sender", n_atoms=1,
            max_atoms_per_core=1)

    @abstractmethod
    def is_multi_cast_source(self):
        """ helper method for is-instance
        :return:
        """
