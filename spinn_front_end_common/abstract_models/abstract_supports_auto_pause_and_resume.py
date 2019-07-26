from spinn_utilities.abstract_base import abstractmethod, AbstractBase
from six import add_metaclass


@add_metaclass(AbstractBase)
class AbstractSupportsAutoPauseAndResume(object):

    @abstractmethod
    def my_local_time_period(
            self, simulator_time_step, time_scale_factor):
        """
        
        :param time_scale_factor: time scale factor
        :param simulator_time_step: the simulator time step
        :return: the time period (machine time step) for this machine vertex
        """