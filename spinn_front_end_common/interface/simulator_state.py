from enum import Enum


class Simulator_State(Enum):
    """ Different states the Simulator could be in.
    """
    INIT = (0, "init called")
    IN_RUN = (1, "inside run method")
    RUN_FOREVER = (2, "finish run method but running forever")
    FINISHED = (3, "run ended shutdown not called")
    SHUTDOWN = (4, "shutdown called")
    STOP_REQUESTED = (5, "stop requested in middle of run forever")

    def __new__(cls, value, doc=""):
        # pylint: disable=protected-access
        obj = object.__new__(cls)
        obj._value_ = value
        obj.__doc__ = doc
        return obj

    def __init__(self, value, doc=""):
        self._value_ = value
        self.__doc__ = doc
