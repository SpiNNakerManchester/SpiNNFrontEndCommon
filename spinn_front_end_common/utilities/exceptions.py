class SpinnFrontEndException(Exception):
    """ Raised when the front end detects an error
    """


class RallocException(SpinnFrontEndException):
    """ Raised when there are not enough routing table entries
    """


class ConfigurationException(SpinnFrontEndException):
    """ Raised when the front end determines a input parameter is invalid
    """


class ExecutableFailedToStartException(SpinnFrontEndException):
    """ Raised when an executable has not entered the expected state during\
        start up
    """


class ExecutableFailedToStopException(SpinnFrontEndException):
    """ Raised when an executable has not entered the expected state during\
        execution
    """


class ExecutableNotFoundException(SpinnFrontEndException):
    """ Raised when a specified executable could not be found
    """


class BufferableRegionTooSmall(SpinnFrontEndException):
    """ Raised when the SDRAM space of the region for buffered packets is\
        too small to contain any packet at all
    """


class BufferedRegionNotPresent(SpinnFrontEndException):
    """ Raised when trying to issue buffered packets for a region not managed
    """
