from enum import Enum
from spinnman.model.enums import CPUState


class ExecutableType(Enum):
    """ supports starting of different types of executables
    """

    RUNNING = (
        0,
        [CPUState.RUNNING],
        [CPUState.FINISHED],
        False,
        "Runs immediately without waiting for barrier and then exits")

    SYNC = (
        1,
        [CPUState.SYNC0],
        [CPUState.FINISHED],
        False,
        "Calls spin1_start(SYNC_WAIT) and then eventually spin1_exit()")

    USES_SIMULATION_INTERFACE = (
        2,
        [CPUState.SYNC0, CPUState.SYNC1, CPUState.PAUSED],
        [CPUState.PAUSED],
        True,
        "Calls simulation_run() and simulation_exit() / "
        "simulation_handle_pause_resume()")

    NO_APPLICATION = (
        3,
        [],
        [],
        True,
        "Situation where there user has supplied no "
        "application but for some reason still wants to run")

    SYSTEM = (
        4,
        [CPUState.RUNNING],
        [CPUState.RUNNING],
        True,
        "Runs immediately without waiting for barrier and never ends"
    )

    def __new__(cls, value, start_state, end_state,
                supports_auto_pause_and_resume, doc=""):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.start_state = start_state
        obj.end_state = end_state
        obj.supports_auto_pause_and_resume = supports_auto_pause_and_resume
        return obj

    def __init__(self, value, start_state, end_state,
                 supports_auto_pause_and_resume, doc=""):
        self._value_ = value
        self.__doc__ = doc
        self.start_state = start_state
        self.end_state = end_state
        self.supports_auto_pause_and_resume = supports_auto_pause_and_resume
