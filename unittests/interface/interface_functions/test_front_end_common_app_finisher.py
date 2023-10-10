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

from spinn_utilities.overrides import overrides
from spinn_machine import CoreSubsets
from spinnman.model.enums import ExecutableType
from spinnman.model.enums.cpu_state import CPUState
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.interface_functions import (
    application_finisher)
from spinnman.model import CPUInfo, CPUInfos
from spinnman.transceiver import Transceiver


class _MockTransceiver(Transceiver):

    def __init__(self, core_states, time_between_states):
        self._core_states = core_states
        self._time_between_states = time_between_states
        self._current_state = 0
        self.sdp_send_count = 0

    @overrides(Transceiver.get_core_state_count)
    def get_core_state_count(self, app_id, state):
        count = 0
        for core_state in self._core_states[self._current_state].values():
            if core_state == state:
                count += 1
        return count

    @overrides(Transceiver.get_cpu_infos)
    def get_cpu_infos(
            self, core_subsets=None, states=None, include=True):
        if states is None or not include:
            raise NotImplementedError("oops")
        cores_in_state = CPUInfos()
        core_states = self._core_states[self._current_state]
        for core_subset in core_subsets:
            x = core_subset.x
            y = core_subset.y

            for p in core_subset.processor_ids:
                if (x, y, p) in core_states:
                    if hasattr(states, "__iter__"):
                        if core_states[x, y, p] in states:
                            cores_in_state.add_info(CPUInfo.mock_info(
                                x, y, p, p, core_states[x, y, p]))
                    elif core_states[x, y, p] == states:
                        cores_in_state.add_info(CPUInfo.mock_info(
                            x, y, p, p, core_states[x, y, p]))

        self._current_state += 1
        return cores_in_state

    @overrides(Transceiver.send_sdp_message)
    def send_sdp_message(self, message, connection=None):
        self.sdp_send_count += 1

    @overrides(Transceiver.send_signal)
    def send_signal(self, app_id, signal):
        pass

    @overrides(Transceiver.close)
    def close(self):
        pass


def test_app_finisher():
    unittest_setup()
    core_subsets = CoreSubsets()
    core_subsets.add_processor(0, 0, 1)
    core_subsets.add_processor(1, 1, 2)
    core_states = [
        {(0, 0, 1): CPUState.RUNNING, (1, 1, 2): CPUState.RUNNING},
        {(0, 0, 1): CPUState.RUNNING, (1, 1, 2): CPUState.FINISHED},
        {(0, 0, 1): CPUState.FINISHED, (1, 1, 2): CPUState.FINISHED}]
    executable_types = {
        ExecutableType.USES_SIMULATION_INTERFACE: core_subsets}
    txrx = _MockTransceiver(core_states, 0.5)
    writer = FecDataWriter.mock()
    writer.set_transceiver(txrx)
    writer.set_executable_types(executable_types)
    application_finisher()

    # First round called twice as 2 running +
    # second round called once as 1 running
    assert txrx.sdp_send_count == 3
