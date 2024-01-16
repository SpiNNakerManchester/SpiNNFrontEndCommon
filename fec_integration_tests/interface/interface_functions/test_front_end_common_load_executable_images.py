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

from typing import BinaryIO, Iterable, Optional, Tuple, Union
import unittest
from collections import defaultdict
from spinn_utilities.overrides import overrides
from spinn_machine import CoreSubsets
from spinnman.transceiver.mockable_transceiver import MockableTransceiver
from spinnman.model import ExecutableTargets
from spinnman.model.enums import CPUState, ExecutableType
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.interface_functions import (
    load_app_images)

SIM = ExecutableType.USES_SIMULATION_INTERFACE


class _MockTransceiver(MockableTransceiver):

    def __init__(self, test_case):
        self._test_case = test_case
        self._n_cores_in_app = defaultdict(lambda: 0)
        self._executable_on_core = dict()

    @overrides(MockableTransceiver.execute_flood)
    def execute_flood(
            self, core_subsets: CoreSubsets,
            executable: Union[BinaryIO, bytes, str], app_id: int, *,
            n_bytes: Optional[int] = None, wait: bool = False
            ):  # @UnusedVariable
        for core_subset in core_subsets.core_subsets:
            x, y = core_subset.x, core_subset.y
            for p in core_subset.processor_ids:
                self._test_case.assertNotIn(
                    (x, y, p), self._executable_on_core)
                self._executable_on_core[x, y, p] = executable
        self._n_cores_in_app[app_id] += len(core_subsets)

    @overrides(MockableTransceiver.get_core_state_count)
    def get_core_state_count(
            self, app_id: int, state: CPUState,
            xys: Optional[Iterable[Tuple[int, int]]] = None
            ) -> int:  # @UnusedVariable
        return self._n_cores_in_app[app_id]


class TestFrontEndCommonLoadExecutableImages(unittest.TestCase):

    def setUp(self):
        unittest_setup()

    def test_front_end_common_load_executable_images(self):
        writer = FecDataWriter.mock()
        writer.set_transceiver(_MockTransceiver(self))
        targets = ExecutableTargets()
        targets.add_processor("test.aplx", 0, 0, 0, SIM)
        targets.add_processor("test.aplx", 0, 0, 1, SIM)
        targets.add_processor("test.aplx", 0, 0, 2, SIM)
        targets.add_processor("test2.aplx", 0, 1, 0, SIM)
        targets.add_processor("test2.aplx", 0, 1, 1, SIM)
        targets.add_processor("test2.aplx", 0, 1, 2, SIM)
        writer.set_executable_targets(targets)
        load_app_images()


if __name__ == "__main__":
    unittest.main()
