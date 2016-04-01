from six import add_metaclass
from abc import ABCMeta
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractMachineAllocationController(object):
    """ An object that controls the allocation of a machine
    """

    @abstractmethod
    def extend_allocation(self, new_total_run_time):
        """ Extend the allocation of the machine from the original\
            run time

        :param new_total_run_time: The total run time that is now required\
                    starting from when the machine was first allocated
        """

    @abstractmethod
    def close(self):
        """ Indicate that the use of the machine is complete
        """
