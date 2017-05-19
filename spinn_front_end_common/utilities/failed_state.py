from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities.simulator_interface \
    import SimulatorInterface


class FailedState(SimulatorInterface):

    @property
    def config(self):
        raise exceptions.ConfigurationException(
            "This call is only valid after SpiNNaker.__init__ has been called")
