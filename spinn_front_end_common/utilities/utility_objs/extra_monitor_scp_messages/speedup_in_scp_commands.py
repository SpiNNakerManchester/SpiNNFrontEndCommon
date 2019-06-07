from enum import Enum


class SpeedupInSCPCommands(Enum):
    """ SCP Command codes for data speed up in
    """
    SAVE_APPLICATION_MC_ROUTES = 6,
    LOAD_APPLICATION_MC_ROUTES = 7,
    LOAD_SYSTEM_MC_ROUTES = 8

    def __new__(cls, value, doc=""):
        # pylint: disable=protected-access, unused-argument
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, value, doc=""):
        self._value_ = value
        self.__doc__ = doc
