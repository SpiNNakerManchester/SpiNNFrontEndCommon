from pacman.executor.injection_decorator import supports_injection,\
    requires_injection, inject


@supports_injection
class NeedsNMachineTimeSteps(object):
    """ A class that uses the number of machine time steps
    """

    def __init__(self):
        self.__n_machine_time_steps = None

    @inject("TotalMachineTimeSteps")
    def set_n_machine_time_steps(self, n_machine_time_steps):
        self.__n_machine_time_steps = n_machine_time_steps

    @property
    @requires_injection(["TotalMachineTimeSteps"])
    def n_machine_time_steps(self):
        return self.__n_machine_time_steps
