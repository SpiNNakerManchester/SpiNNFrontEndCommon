from enum import Enum


class DPRIFlags(Enum):
    """ SCP Dropped Packet Reinjection Packet type flags
    """
    MULTICAST = 1
    POINT_TO_POINT = 2
    NEAREST_NEIGHBOUR = 4
    FIXED_ROUTE = 8

    def __new__(cls, value, doc=""):
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, value, doc=""):
        self._value_ = value
        self.__doc__ = doc
