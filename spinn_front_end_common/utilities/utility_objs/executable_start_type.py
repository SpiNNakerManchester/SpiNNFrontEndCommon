from enum import Enum


class ExecutableStartType(Enum):
    """ supports starting of different types of executables
    """

    RUNNING = (
        0, "Runs immediately without waiting for barrier and then exits")
    SYNC = (
        1, "Calls spin1_start(SYNC_WAIT) and then eventually spin1_exit()")
    USES_SIMULATION_INTERFACE = (
        2,
        "Calls simulation_run() and simulation_exit() / "
        "simulation_handle_pause_resume()")

    def __new__(cls, value, doc=""):
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, value, doc=""):
        self._value_ = value
        self.__doc__ = doc
