from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities.simulator_interface \
    import SimulatorInterface


class FailedState(SimulatorInterface):

    @staticmethod
    def add_socket_address(self, x):
        raise exceptions.ConfigurationException(
            "This call is only valid between setup and end/stop")

    @property
    def buffer_manager(self):
        raise exceptions.ConfigurationException(
            "This call is only valid between setup and end/stop")

    @property
    def config(self):
        raise exceptions.ConfigurationException(
            "This call is only valid between setup and end/stop")

    @property
    def graph_mapper(self):
        raise exceptions.ConfigurationException(
            "This call is only valid between setup and end/stop")

    @property
    def graph_mapper(self):
        raise exceptions.ConfigurationException(
            "This call is only valid between setup and end/stop")

    @property
    def has_ran(self):
        raise exceptions.ConfigurationException(
            "This call is only valid between setup and end/stop")

    @property
    def has_ran(self):
        raise exceptions.ConfigurationException(
            "This call is only valid between setup and end/stop")

    @property
    def increment_none_labelled_vertex_count(self):
        raise exceptions.ConfigurationException(
            "This call is only valid between setup and end/stop")

    @property
    def machine(self):
        raise exceptions.ConfigurationException(
            "This call is only valid between setup and end/stop")

    @property
    def machine_time_step(self):
        raise exceptions.ConfigurationException(
            "This call is only valid between setup and end/stop")

    @property
    def placements(self):
        raise exceptions.ConfigurationException(
            "This call is only valid between setup and end/stop")

    def stop(self):
        raise exceptions.ConfigurationException(
            "You cannot call end/stop until you have called setup "
            "or after end/stop has been called.")

    @property
    def transceiver(self):
        raise exceptions.ConfigurationException(
            "This call is only valid between setup and end/stop")


