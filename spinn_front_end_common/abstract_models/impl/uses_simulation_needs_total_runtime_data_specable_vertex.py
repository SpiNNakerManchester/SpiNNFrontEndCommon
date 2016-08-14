from spinn_front_end_common.abstract_models.\
    abstract_generates_data_specification import \
    AbstractGeneratesDataSpecification
from spinn_front_end_common.abstract_models.\
    abstract_has_associated_binary import \
    AbstractHasAssociatedBinary

from pacman.executor.injection_decorator import \
    supports_injection, inject

import threading

# used to stop file conflicts
from spinn_front_end_common.interface.simulation.impl.\
    uses_simulation_impl import UsesSimulationImpl

_lock_condition = threading.Condition()


@supports_injection
class UsesSimulationNeedsTotalRuntimeDataSpecableVertex(
        AbstractGeneratesDataSpecification, AbstractHasAssociatedBinary,
        UsesSimulationImpl):

    __slots__ = [
        # the number of machine time steps expected to be ran during
        # this simulation (int)
        "_no_machine_time_steps"
    ]

    def __init__(self, machine_time_step, time_scale_factor):
        AbstractGeneratesDataSpecification.__init__(self)
        AbstractHasAssociatedBinary.__init__(self)
        UsesSimulationImpl.__init__(self, machine_time_step, time_scale_factor)
        self._no_machine_time_steps = None

    @inject("MemoryNoMachineTimeSteps")
    def set_no_machine_time_steps(self, n_machine_time_steps):
        self._no_machine_time_steps = n_machine_time_steps


