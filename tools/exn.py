class BadArgs(Exception):
    """ Bad number of arguments to a command.
    """
    def __str__(self):
        return "bad args"


class StructParseException(Exception):
    """ Parsing exception handling structure definition. """


class SpinnException(Exception):
    """ General exception from the comms layer or SpiNNaker. """
