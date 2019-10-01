from spinn_utilities.abstract_base import abstractmethod, AbstractBase
from six import add_metaclass


@add_metaclass(AbstractBase)
class AbstractApplicationSupportsAutoPauseAndResume(object):

    @abstractmethod
    def my_variable_local_time_period(
            self, default_machine_time_step, variable):
        """ allows an application vertex to define a time step per recorded /
        variable

        :param default_machine_time_step: the simulator time step
        :param variable: the variable to ask about time step for
        :return: the time period (machine time step) for this machine vertex
        """
