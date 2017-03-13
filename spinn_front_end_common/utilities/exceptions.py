class SpinnFrontEndException(Exception):
    """ Raised when the front end detects an error
    """
    pass


class RallocException(SpinnFrontEndException):
    """ Raised when there are not enough routing table entries
    """
    pass


class ConfigurationException(SpinnFrontEndException):
    """ Raised when the front end determines a input param is invalid
    """
    pass


class ExecutableFailedToStartException(SpinnFrontEndException):
    """ Raised when an executable has not entered the expected state during\
        start up
    """
    pass


class ExecutableFailedToStopException(SpinnFrontEndException):
    """ Raised when an executable has not entered the expected state during\
        execution
    """
    pass


class ExecutableNotFoundException(SpinnFrontEndException):
    """ Raised when a specified executable could not be found
    """
    pass


class BufferableRegionTooSmall(SpinnFrontEndException):
    """ Raised when the SDRAM space of the region for buffered packets is\
        too small to contain any packet at all
    """
    pass


class BufferedRegionNotPresent(SpinnFrontEndException):
    """ Raised when trying to issue buffered packets for a region not managed
    """
    pass
