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
from spinn_utilities.progress_bar import ProgressBar
from spinnman.model.enums import CPUState
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utilities.scp import UpdateRuntimeProcess


def chip_runtime_updater(n_sync_steps):
    """ Updates the runtime of an application running on a SpiNNaker machine.

        :param n_sync_steps:
        :type n_sync_steps: int or None
    """
    core_subsets = FecDataView.get_executable_types()[
        ExecutableType.USES_SIMULATION_INTERFACE]

    ready_progress = ProgressBar(
        total_number_of_things_to_do=1,
        string_describing_what_being_progressed=(
            "Waiting for cores to be either in PAUSED or READY state"))
    FecDataView.get_transceiver().wait_for_cores_to_be_in_state(
        core_subsets, FecDataView.get_app_id(),
        [CPUState.PAUSED, CPUState.READY],
        error_states=frozenset({
            CPUState.RUN_TIME_EXCEPTION, CPUState.WATCHDOG,
            CPUState.FINISHED}))
    ready_progress.end()

    run_until_timesteps = FecDataView.get_current_run_timesteps()
    if run_until_timesteps is None:
        infinite_run = 1
        run_until_timesteps = 0
        current_timesteps = 0
    else:
        infinite_run = 0
        current_timesteps = FecDataView.get_first_machine_time_step()

    process = UpdateRuntimeProcess(FecDataView.get_scamp_connection_selector())
    process.update_runtime(
        current_timesteps, run_until_timesteps, infinite_run, core_subsets,
        len(core_subsets), n_sync_steps)
