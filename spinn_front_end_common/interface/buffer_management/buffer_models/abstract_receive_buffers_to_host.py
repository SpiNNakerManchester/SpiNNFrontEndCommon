from abc import ABCMeta
from abc import abstractmethod
from six import add_metaclass


@add_metaclass(ABCMeta)
class AbstractReceiveBuffersToHost(object):
    """ Indicates that this object can receive buffers
    """

    @abstractmethod
    def buffering_output(self):
        """ True if the output buffering mechanism is activated

        :return: Boolean indicating whether the output buffering mechanism\
                is activated
        :rtype: bool
        """

    @abstractmethod
    def get_minimum_buffer_sdram_usage(self):
        """ Get the minimum amount of SDRAM to reserve for buffers
        """

    @abstractmethod
    def get_n_timesteps_in_buffer_space(self, buffer_space):
        """ Get the number of timesteps that can be stored fully in the given\
            buffer space in bytes

        :param buffer_space The buffer space in bytes
        :return: The number of time steps that can be stored in the buffer
        :rtype: int
        """

    @abstractmethod
    def get_buffered_regions(self):
        """ Get the regions that have been recorded using buffering

        :return: The region numbers that have active recording
        :rtype: iterable of int
        """

    @abstractmethod
    def get_buffered_state_region(self):
        """ Get the state region for buffered recording

        :return: The buffered state region
        :rtype: int
        """
