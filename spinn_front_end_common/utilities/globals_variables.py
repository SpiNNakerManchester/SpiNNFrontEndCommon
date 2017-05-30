
_failed_state = None
_simulator = None


def get_simulator():
    global _simulator, _failed_state
    if _simulator is None:
        if _failed_state is None:
            raise ValueError("You must import one of the simulator classes "
                             "before calling get_simulator")
        return _failed_state
    return _simulator


def set_simulator(new_simulator):
    global _simulator, _failed_state
    if _failed_state is None:
        raise ValueError("Unexpected call to set_simulator before "
                         "set_failed_state")
    _simulator = new_simulator


def unset_simulator():
    global _simulator
    _simulator = None


def has_simulator():
    global _simulator
    return _simulator is not None


def set_failed_state(new_failed_state):
    global _failed_state
    if _failed_state is None:
        _failed_state = new_failed_state
    else:
        if type(new_failed_state) != type(_failed_state):
            raise ValueError("You may only setup/init one type of simulator")
