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
    def __init__(self, output_string, failed_core_subsets):
        SpinnFrontEndException.__init__(self, output_string)
        self._failed_core_subsets = failed_core_subsets

    @property
    def failed_core_subsets(self):
        """ The subset of cores in the incorrect state
        """
        return self._failed_core_subsets


class ExecutableFailedToStopException(SpinnFrontEndException):
    """ Raised when an executable has not entered the expected state during\
        execution
    """
    def __init__(self, output_string, failed_core_subsets, is_rte):
        SpinnFrontEndException.__init__(self, output_string)
        self._failed_core_subsets = failed_core_subsets
        self._is_rte = is_rte

    @property
    def failed_core_subsets(self):
        """ The failed cores
        """
        return self._failed_core_subsets

    @property
    def is_rte(self):
        """ True if the failure was an RTE
        """
        return self._is_rte


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
