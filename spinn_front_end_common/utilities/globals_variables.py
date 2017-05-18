from spinn_front_end_common.utilities.failed_state import FailedState

failed_state = FailedState()
simulator = None


def get_simulator():
    global simulator, failed_state
    if simulator is None:
        return failed_state
    return simulator


def set_simulator(new_simulator):
    global simulator
    simulator = new_simulator


def unset_simulator():
    global simulator
    simulator = None


def set_failed_state(new_failed_state):
    global failed_state
    failed_state = new_failed_state

