from spinn_front_end_common.utilities.exceptions import ConfigurationException
from .simulator_interface import SimulatorInterface

FAILED_STATE_MSG = "This call is only valid between setup and end/stop"


class FailedState(SimulatorInterface):

    @staticmethod
    def add_socket_address(self, x):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    def buffer_manager(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    def config(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    def graph_mapper(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    def has_ran(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    def increment_none_labelled_vertex_count(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    def machine(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    def machine_time_step(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    def no_machine_time_steps(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    def none_labelled_vertex_count(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    def placements(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    def run(self, run_time):
        raise ConfigurationException(FAILED_STATE_MSG)

    def stop(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    def transceiver(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    @property
    def use_virtual_board(self):
        raise ConfigurationException(FAILED_STATE_MSG)

    def verify_not_running(self):
        raise ConfigurationException(FAILED_STATE_MSG)
