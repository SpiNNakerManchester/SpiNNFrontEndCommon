from spinn_utilities.abstract_base import abstractmethod, AbstractBase
from six import add_metaclass


@add_metaclass(AbstractBase)
class AbstractMachineSupportsAutoPauseAndResume(object):

    @abstractmethod
    def my_local_time_period(self, simulator_time_step):
        """ allows a machine vertex to define its time step

        :param simulator_time_step: the simulator time step
        :return: the time period (machine time step) for this machine vertex
        """
