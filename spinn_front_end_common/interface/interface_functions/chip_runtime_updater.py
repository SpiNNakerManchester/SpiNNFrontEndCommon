# Copyright (c) 2015 The University of Manchester
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
from spinn_utilities.progress_bar import ProgressBar
from spinnman.model.enums import CPUState, ExecutableType
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.scp import UpdateRuntimeProcess


def chip_runtime_updater(n_sync_steps: int) -> None:
    """
    Updates the runtime of an application running on a SpiNNaker machine.

    :param n_sync_steps:
    """
    core_subsets = FecDataView.get_cores_for_type(
        ExecutableType.USES_SIMULATION_INTERFACE)
    n_cores = len(core_subsets)
    with ProgressBar(
            n_cores, "Waiting for cores to be either in "
            "PAUSED or READY state") as progress:
        FecDataView.get_transceiver().wait_for_cores_to_be_in_state(
            core_subsets, FecDataView.get_app_id(),
            frozenset([CPUState.PAUSED, CPUState.READY]),
            error_states=frozenset({
                CPUState.RUN_TIME_EXCEPTION, CPUState.WATCHDOG,
                CPUState.FINISHED}), progress_bar=progress,
            timeout=n_cores)

    run_until_timesteps = FecDataView.get_current_run_timesteps()
    first_timestep = FecDataView.get_first_machine_time_step()
    if run_until_timesteps is None:
        infinite_run = True
        run_until_timesteps = 0
    else:
        infinite_run = False

    process = UpdateRuntimeProcess(FecDataView.get_scamp_connection_selector())
    process.update_runtime(
        first_timestep, run_until_timesteps, infinite_run, core_subsets,
        len(core_subsets), n_sync_steps)
