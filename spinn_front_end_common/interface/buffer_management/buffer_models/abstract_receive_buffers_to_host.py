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
    def get_recording_region_base_address(
            self, recording_region_id, txrx, placement):
        """ get the recording base address from the recording region id.

        :param recording_region_id:\
            the recording region id to find the base address of
        :param txrx: the SpiNNMan instance
        :param placement:\
            the placement object of the core to find the address of
        :return: the base address as a int of that recording region
        """
