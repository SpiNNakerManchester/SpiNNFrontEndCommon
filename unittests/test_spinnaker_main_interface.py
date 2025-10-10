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
from typing import Tuple

import unittest

from spinn_utilities.exceptions import SimulatorShutdownException
from spinn_utilities.overrides import overrides

from spinnman.spalloc import MachineAllocationController

from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.abstract_spinnaker_base import (
    AbstractSpinnakerBase)


class Close_Once(MachineAllocationController):
    __slots__ = ("closed", )

    def __init__(self) -> None:
        super().__init__("close-once")
        self.closed = False

    @overrides(MachineAllocationController._wait)
    def _wait(self) -> bool:
        return False

    @overrides(MachineAllocationController.close)
    def close(self) -> None:
        if self.closed:
            raise NotImplementedError("Close called twice")
        self.closed = True
        super().close()

    @overrides(MachineAllocationController.extend_allocation)
    def extend_allocation(self, new_total_run_time: float) -> None:
        pass

    @overrides(MachineAllocationController.where_is_machine)
    def where_is_machine(
            self, chip_x: int, chip_y: int) -> Tuple[int, int, int]:
        return (0, 0, 0)


class TestSpinnakerMainInterface(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        unittest_setup()

    def test_stop_init(self) -> None:
        class_file = sys.modules[self.__module__].__file__
        assert class_file is not None
        path = os.path.dirname(os.path.abspath(class_file))
        assert path is not None
        os.chdir(path)
        interface = AbstractSpinnakerBase()
        mock_contoller = Close_Once()
        interface._data_writer.set_allocation_controller(mock_contoller)
        self.assertFalse(mock_contoller.closed)
        interface.stop()
        self.assertTrue(mock_contoller.closed)
        with self.assertRaises(SimulatorShutdownException):
            interface.stop()

    def test_min_init(self) -> None:
        class_file = sys.modules[self.__module__].__file__
        assert class_file is not None
        path = os.path.dirname(os.path.abspath(class_file))
        assert path is not None
        os.chdir(path)
        AbstractSpinnakerBase()


if __name__ == "__main__":
    unittest.main()
