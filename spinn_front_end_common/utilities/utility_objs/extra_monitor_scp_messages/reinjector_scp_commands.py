from enum import Enum


class ReinjectorSCPCommands(Enum):
    """ SCP Command codes for reinjection
    """
    SET_ROUTER_TIMEOUT = 0
    SET_ROUTER_EMERGENCY_TIMEOUT = 1
    SET_PACKET_TYPES = 2
    GET_STATUS = 3
    RESET_COUNTERS = 4
    EXIT = 5
    CLEAR = 6

    def __new__(cls, value, doc=""):
        # pylint: disable=protected-access, unused-argument
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, value, doc=""):
        self._value_ = value
        self.__doc__ = doc
