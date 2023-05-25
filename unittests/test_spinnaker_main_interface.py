# Copyright (c) 2017 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import unittest
from spinn_utilities.exceptions import SimulatorShutdownException
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.abstract_spinnaker_base import (
    AbstractSpinnakerBase)
from spinn_front_end_common.abstract_models.impl import (
    MachineAllocationController)


class Close_Once(MachineAllocationController):
    __slots__ = ("closed", )

    def __init__(self):
        super().__init__("close-once")
        self.closed = False

    def _wait(self):
        return False

    def close(self):
        if self.closed:
            raise NotImplementedError("Close called twice")
        self.closed = True
        super().close()

    def extend_allocation(self, new_total_run_time):
        pass

    def where_is_machine(self, chip_x, chip_y):
        return (0, 0, 0)


class TestSpinnakerMainInterface(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        unittest_setup()

    def test_stop_init(self):
        class_file = sys.modules[self.__module__].__file__
        path = os.path.dirname(os.path.abspath(class_file))
        os.chdir(path)
        interface = AbstractSpinnakerBase()
        mock_contoller = Close_Once()
        # pylint: disable=protected-access
        interface._data_writer.set_allocation_controller(mock_contoller)
        self.assertFalse(mock_contoller.closed)
        interface.stop()
        self.assertTrue(mock_contoller.closed)
        with self.assertRaises(SimulatorShutdownException):
            interface.stop()

    def test_min_init(self):
        class_file = sys.modules[self.__module__].__file__
        path = os.path.dirname(os.path.abspath(class_file))
        os.chdir(path)
        AbstractSpinnakerBase()


if __name__ == "__main__":
    unittest.main()
