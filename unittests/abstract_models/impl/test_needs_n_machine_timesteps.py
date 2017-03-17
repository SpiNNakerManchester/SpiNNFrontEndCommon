import unittest
from pacman.executor import injection_decorator
from spinn_front_end_common.abstract_models.impl.needs_n_machine_time_steps \
    import NeedsNMachineTimeSteps


class TestNeedsNMachineTimeSteps(unittest.TestCase):

    def test_injection(self):
        obj = NeedsNMachineTimeSteps()
        with injection_decorator.injection_context(
                {"TotalMachineTimeSteps": 10}):
            self.assertEqual(obj._n_machine_time_steps, 10)

if __name__ == "__main__":
    unittest.main()
