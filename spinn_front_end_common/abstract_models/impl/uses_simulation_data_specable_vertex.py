from spinn_front_end_common.abstract_models.\
    abstract_generates_data_specification import \
    AbstractGeneratesDataSpecification
from spinn_front_end_common.abstract_models.\
    abstract_has_associated_binary import \
    AbstractHasAssociatedBinary

import threading

# used to stop file conflicts
from spinn_front_end_common.interface.simulation.impl.\
    uses_simulation_impl import UsesSimulationImpl

_lock_condition = threading.Condition()


class UsesSimulationDataSpecableVertex(
        AbstractGeneratesDataSpecification, AbstractHasAssociatedBinary,
        UsesSimulationImpl):

    __slots__ = []

    def __init__(self, machine_time_step, time_scale_factor):
        AbstractGeneratesDataSpecification.__init__(self)
        AbstractHasAssociatedBinary.__init__(self)
        UsesSimulationImpl.__init__(self, machine_time_step, time_scale_factor)


