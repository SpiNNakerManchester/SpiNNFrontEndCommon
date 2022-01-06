# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from spinn_utilities.overrides import overrides
from spinn_machine import CoreSubsets
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinnman.model.enums.cpu_state import CPUState
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.interface_functions import (
    application_finisher)
from spinnman.model.cpu_infos import CPUInfos
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

    @overrides(Transceiver.get_cores_in_state)
    def get_cores_in_state(self, all_core_subsets, states):
        cores_in_state = CPUInfos()
        core_states = self._core_states[self._current_state]
        for core_subset in all_core_subsets:
            x = core_subset.x
            y = core_subset.y

            for p in core_subset.processor_ids:
                if (x, y, p) in core_states:
                    if hasattr(states, "__iter__"):
                        if core_states[x, y, p] in states:
                            cores_in_state.add_processor(x, y, p, None)
                    elif core_states[x, y, p] == states:
                        cores_in_state.add_processor(x, y, p, None)

        self._current_state += 1
        return cores_in_state

    @overrides(Transceiver.send_sdp_message)
    def send_sdp_message(self, message, connection=None):
        self.sdp_send_count += 1

    @overrides(Transceiver.send_signal)
    def send_signal(self, app_id, signal):
        pass

    @overrides(Transceiver.close)
    def close(self, close_original_connections=True, power_off_machine=False):
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
    FecDataWriter.mock().set_transceiver(txrx)
    application_finisher(executable_types)

    # First round called twice as 2 running +
    # second round called once as 1 running
    assert txrx.sdp_send_count == 3
