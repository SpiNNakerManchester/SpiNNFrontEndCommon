class SpinnFrontEndException(Exception):
    """rasied when the pynn front end detects that a routing error has occurred
    (during multicast soruce)

    :raise None: does not raise any known exceptions
    """
    pass


class RallocException(SpinnFrontEndException):
    """rasied when the pynn front end detects that a routing error has occurred
    (during multicast soruce)

    :raise None: does not raise any known exceptions
    """
    pass


class ConfigurationException(SpinnFrontEndException):
    """raised when the pynn front end determines a input param is invalid

    :raise None: does not raise any known exceptions"""
    pass


class ExecutableFailedToStartException(SpinnFrontEndException):
    """ raised when the messgaes from the trnasicever state that some or all
    the application images pushed to the board have failed to start when asked


    :raise None: does not raise any known exceptions
    """
    pass


class ExecutableFailedToStopException(SpinnFrontEndException):
    """ raised when the messgaes from the trnasicever state that some or all
    the application images pushed to the board have failed to stop when
    expected


    :raise None: does not raise any known exceptions
    """
    pass


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
