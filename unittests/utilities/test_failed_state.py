import unittest

from spinn_front_end_common.utilities.failed_state import FailedState
from spinn_front_end_common.utilities import globals_variables
from spinn_front_end_common.utilities.simulator_interface \
    import SimulatorInterface


class SimulatorInterfaceStub(SimulatorInterface):

    @property
    def config(self):
        return "STUB!"


class TestFailedState(unittest.TestCase):

    def test_init(self):
        fs = FailedState()
        self.assertIsNotNone(fs)

    def test_globals_variable(self):
        sim = globals_variables.get_simulator()
        self.assertTrue(isinstance(sim, FailedState))

    def test_set_failed_State(self):
        fs_new = SimulatorInterfaceStub()
        globals_variables.set_failed_state(fs_new)
        sim = globals_variables.get_simulator()
        self.assertTrue(isinstance(sim, SimulatorInterfaceStub))

        # Make sure to set it back for other tests
        fs = FailedState()
        globals_variables.set_failed_state(fs)
        sim = globals_variables.get_simulator()
        self.assertTrue(isinstance(sim, FailedState))

    def test_set_sim(self):
        globals_variables.set_simulator("BOO")
        sim = globals_variables.get_simulator()
        self.assertTrue(isinstance(sim, str))

        # Make sure to set it back for other tests
        globals_variables.unset_simulator()
        sim = globals_variables.get_simulator()
        self.assertTrue(isinstance(sim, FailedState))
