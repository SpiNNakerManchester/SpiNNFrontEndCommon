class HasNMachineTimesteps(object):
    """ An object that has a number of machine timesteps associated with it
    """

    def __init__(self, n_machine_timesteps=None):
        self._n_machine_timesteps = n_machine_timesteps

    @property
    def n_machine_timesteps(self):
        return self._n_machine_timesteps

    @n_machine_timesteps.setter
    def n_machine_timesteps(self, n_machine_timesteps):
        self._n_machine_timesteps = n_machine_timesteps
