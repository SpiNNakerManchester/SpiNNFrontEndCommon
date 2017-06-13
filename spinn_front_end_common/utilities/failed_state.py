from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities.simulator_interface \
    import SimulatorInterface

FAILED_STATE_MSG = "This call is only valid between setup and end/stop"


class FailedState(SimulatorInterface):

    @staticmethod
    def add_socket_address(self, x):
        raise exceptions.ConfigurationException(FAILED_STATE_MSG)

    @property
    def buffer_manager(self):
        raise exceptions.ConfigurationException(FAILED_STATE_MSG)

    @property
    def config(self):
        raise exceptions.ConfigurationException(FAILED_STATE_MSG)

    @property
    def graph_mapper(self):
        raise exceptions.ConfigurationException(FAILED_STATE_MSG)

    @property
    def has_ran(self):
        raise exceptions.ConfigurationException(FAILED_STATE_MSG)

    @property
    def increment_none_labelled_vertex_count(self):
        raise exceptions.ConfigurationException(FAILED_STATE_MSG)

    @property
    def machine(self):
        raise exceptions.ConfigurationException(FAILED_STATE_MSG)

    @property
    def machine_time_step(self):
        raise exceptions.ConfigurationException(FAILED_STATE_MSG)

    @property
    def no_machine_time_steps(self):
        raise exceptions.ConfigurationException(FAILED_STATE_MSG)

    @property
    def none_labelled_vertex_count(self):
        raise exceptions.ConfigurationException(FAILED_STATE_MSG)

    @property
    def placements(self):
        raise exceptions.ConfigurationException(FAILED_STATE_MSG)

    def run(self, run_time):
        raise exceptions.ConfigurationException(FAILED_STATE_MSG)

    def stop(self):
        raise exceptions.ConfigurationException(FAILED_STATE_MSG)

    @property
    def transceiver(self):
        raise exceptions.ConfigurationException(FAILED_STATE_MSG)

    @property
    def use_virtual_board(self):
        raise exceptions.ConfigurationException(FAILED_STATE_MSG)
