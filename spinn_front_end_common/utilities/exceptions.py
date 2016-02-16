class SpinnFrontEndException(Exception):
    """raised when the PyNN front end detects that a routing error has occurred
    (during multicast source)

    :raise None: does not raise any known exceptions
    """
    pass


class RallocException(SpinnFrontEndException):
    """raised when the PyNN front end detects that a routing error has occurred
    (during multicast source)

    :raise None: does not raise any known exceptions
    """
    pass


class ConfigurationException(SpinnFrontEndException):
    """raised when the PyNN front end determines a input param is invalid

    :raise None: does not raise any known exceptions"""
    pass


class ExecutableFailedToStartException(SpinnFrontEndException):
    """ raised when the messages from the transceiver state that some or all
    the application images pushed to the board have failed to start when asked


    :raise None: does not raise any known exceptions
    """
    def __init__(self, output_string, failed_core_subsets):
        SpinnFrontEndException.__init__(self, output_string)
        self._failed_core_subsets = failed_core_subsets

    @property
    def failed_core_subsets(self):
        """
        property method for returning data from a failed to start exception
        :return:
        """
        return self._failed_core_subsets


class ExecutableFailedToStopException(SpinnFrontEndException):
    """ raised when the messages from the transceiver state that some or all
    the application images pushed to the board have failed to stop when
    expected


    :raise None: does not raise any known exceptions
    """
    def __init__(self, output_string, failed_core_subsets):
        SpinnFrontEndException.__init__(self, output_string)
        self._failed_core_subsets = failed_core_subsets

    @property
    def failed_core_subsets(self):
        """
        property method for returning data from a failed to stop exception
        :return:
        """
        return self._failed_core_subsets


class ExecutableNotFoundException(SpinnFrontEndException):
    """ raised when a suitable executable cannot be found
    to load onto SpiNNaker for a particular vertex


    :raise None: does not raise any known exceptions
    """
    pass


class BufferableRegionTooSmall(SpinnFrontEndException):
    """ raised when the SDRAM space of the region for buffered packets is
    too small to contain any packet at all
    """
    pass


class BufferedRegionNotPresent(SpinnFrontEndException):
    """ raised when trying to issue buffered packets for a region not managed
    """
    pass
