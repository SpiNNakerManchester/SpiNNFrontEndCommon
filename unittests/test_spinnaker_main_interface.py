import os
import sys
import unittest

import spinn_front_end_common.interface.abstract_spinnaker_base as base
from spinn_front_end_common.interface.abstract_spinnaker_base \
    import AbstractSpinnakerBase
from spinn_front_end_common.utilities.utility_objs import ExecutableFinder
from spinn_front_end_common.utilities import globals_variables
from spinn_front_end_common.utilities import FailedState


class Close_Once(object):

    __slots__ = ("closed")

    def __init__(self):
        self.closed = False

    def close(self):
        if self.closed:
            raise Exception("Close called twice")
        else:
            self.closed = True


class MainInterfaceTimingImpl(AbstractSpinnakerBase):

    def __init__(self, machine_time_step=None, time_scale_factor=None):
        AbstractSpinnakerBase.__init__(
            self, base.CONFIG_FILE, ExecutableFinder())
        self.set_up_timings(machine_time_step, time_scale_factor)


class TestSpinnakerMainInterface(unittest.TestCase):

    def setUp(self):
        globals_variables.set_failed_state(FailedState())

    def test_min_init(self):
        class_file = sys.modules[self.__module__].__file__
        path = os.path.dirname(os.path.abspath(class_file))
        os.chdir(path)
        AbstractSpinnakerBase(base.CONFIG_FILE, ExecutableFinder())

    def test_stop_init(self):
        class_file = sys.modules[self.__module__].__file__
        path = os.path.dirname(os.path.abspath(class_file))
        os.chdir(path)
        interface = AbstractSpinnakerBase(base.CONFIG_FILE, ExecutableFinder())
        mock_contoller = Close_Once()
        interface._machine_allocation_controller = mock_contoller
        self.assertFalse(mock_contoller.closed)
        interface.stop(turn_off_machine=False, clear_routing_tables=False,
                       clear_tags=False)
        self.assertTrue(mock_contoller.closed)
        interface.stop(turn_off_machine=False, clear_routing_tables=False,
                       clear_tags=False)

    def test_timings(self):

        # Test defaults
        interface = MainInterfaceTimingImpl()
        assert interface.machine_time_step == 1000
        assert interface.timescale_factor is None

        # Test specified
        interface = MainInterfaceTimingImpl(200, 10)
        assert interface.machine_time_step == 200
        assert interface.timescale_factor == 10


if __name__ == "__main__":
    unittest.main()
