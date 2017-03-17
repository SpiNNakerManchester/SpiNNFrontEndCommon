from pacman.executor.injection_decorator import inject_items


class NeedsNMachineTimeSteps(object):
    """ A class that uses the number of machine time steps
    """

    __slots__ = ()

    @property
    @inject_items({"total_machine_time_steps": "TotalMachineTimeSteps"})
    def _n_machine_time_steps(self, total_machine_time_steps):
        return total_machine_time_steps
