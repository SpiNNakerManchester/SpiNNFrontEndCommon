from pacman.executor.injection_decorator import supports_injection
from pacman.executor.injection_decorator import inject


@supports_injection
class NeedsNMachineTimeSteps(object):
    """ A class that uses the number of machine time steps
    """

    def __init__(self):
        self._n_machine_time_steps = None

    @inject("TotalMachineTimeSteps")
    def set_n_machine_time_steps(self, n_machine_time_steps):
        self._n_machine_time_steps = n_machine_time_steps
