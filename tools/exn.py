class BadArgs(Exception):
    """ Bad number of arguments to a command.
    """
    def __str__(self):
        return "bad args"


class SpinnException(Exception):
    """ General exception from the comms layer or SpiNNaker. """
