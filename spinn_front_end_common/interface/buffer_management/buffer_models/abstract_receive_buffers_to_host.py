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
    def get_recorded_region_ids(self):
        """ Get the recording region ids that have been recorded using buffering

        :return: The region numbers that have active recording
        :rtype: iterable of int
        """

    @abstractmethod
    def get_buffered_state_address(self, txrx, placement):
        """ Get the address where the buffer state data is stored

        :param txrx: the SpiNNMan instance
        :param placement: the placement to find the state address for
        :return: int which is the memory address
        """
