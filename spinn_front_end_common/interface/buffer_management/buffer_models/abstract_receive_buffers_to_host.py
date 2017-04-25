from six import add_metaclass

from spinn_utilities.abstract_base import AbstractBase, abstractmethod


@add_metaclass(AbstractBase)
class AbstractReceiveBuffersToHost(object):
    """ Indicates that this object can receive buffers
    """

    __slots__ = ()

    @abstractmethod
    def get_minimum_buffer_sdram_usage(self):
        """ Get the minimum amount of SDRAM to reserve for buffers
        """

    @abstractmethod
    def get_n_timesteps_in_buffer_space(self, buffer_space, machine_time_step):
        """ Get the number of timesteps that can be stored fully in the given\
            buffer space in bytes

        :param buffer_space: The buffer space in bytes
        :param machine_time_step: The size of each time step
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
    def get_recording_region_base_address(self, txrx, placement):
        """ Get the recording region base address

        :param txrx: the SpiNNMan instance
        :param placement:\
            the placement object of the core to find the address of
        :return: the base address of the recording region
        """
