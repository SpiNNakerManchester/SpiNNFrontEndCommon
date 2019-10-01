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
from collections import defaultdict

from spinn_front_end_common.utilities.constants import \
    MICRO_TO_MILLISECOND_CONVERSION
from spinn_machine import CoreSubsets
from spinn_utilities.progress_bar import ProgressBar
from spinnman.model.enums import CPUState
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utilities.scp import UpdateRuntimeProcess


class ChipRuntimeUpdater(object):
    """ Updates the runtime of an application running on a SpiNNaker machine.
    """

    __slots__ = []

    @staticmethod
    def _determine_true_core_subsets(
            core_subsets, placements, local_machine_time_step_map, run_time,
            current_timestep_map):
        """ determine correct set of core subsets for correct run times

        :param core_subsets: total core subsets of simulation interface
        :param placements: placements
        :param local_machine_time_step_map: map of vertex to local machine \
        time step
        :param run_time: the runtime for this step
        :param current_timestep_map: the map of vertex to current timestep map
        :return: a dict of (
        """
        subsets_with_same_data = defaultdict(CoreSubsets)
        for core_subset in core_subsets:
            for processor_id in core_subset.processor_ids:
                vertex = placements.get_vertex_on_processor(
                    core_subset.x, core_subset.y, processor_id)
                machine_time_step = local_machine_time_step_map[vertex]

                # the next number of machine steps to do
                next_n_machine_time_steps = (
                    (run_time * MICRO_TO_MILLISECOND_CONVERSION) /
                    machine_time_step)

                # where we should be at now
                if vertex in current_timestep_map:
                    (_, this_core_current_point) = (
                        current_timestep_map[vertex])
                else:
                    this_core_current_point = 0

                # the next point to stop at
                next_point = int(
                    this_core_current_point + (next_n_machine_time_steps))
                subsets_with_same_data[
                    (this_core_current_point, next_point)].add_processor(
                    core_subset.x, core_subset.y, processor_id)

                # update the new current time step
                current_timestep_map[vertex] = (
                    this_core_current_point, next_point)

        return subsets_with_same_data

    @staticmethod
    def _set_off_infinite_run(txrx, core_subsets):
        """ sets off a infinite run chip update

        :param txrx: spinnman instance
        :param core_subsets: the cores which run the simulation interface
        :rtype: None
        """
        # TODO: Expose the connection selector in SpiNNMan
        process = UpdateRuntimeProcess(txrx.scamp_connection_selector)
        process.update_runtime(
            current_time=0, run_time=0, infinite_run=1,
            core_subsets=core_subsets, n_cores=len(core_subsets))

    @staticmethod
    def _set_off_next_step(same_data, txrx):
        """ set off another step stage

        :param same_data: the maps of current time step and the next point \
        with cores
        :param txrx: spinnman instance
        :rtype: None
        """
        for (this_core_current_point, next_point) in same_data.keys():
            process = UpdateRuntimeProcess(txrx.scamp_connection_selector)
            process.update_runtime(
                current_time=this_core_current_point, run_time=next_point,
                infinite_run=0,
                core_subsets=same_data[(this_core_current_point, next_point)],
                n_cores=len(same_data[(this_core_current_point, next_point)]))

    def __call__(
            self, txrx, app_id, executable_types, current_timestep_map,
            run_time, local_machine_time_step_map, placements):

        core_subsets = \
            executable_types[ExecutableType.USES_SIMULATION_INTERFACE]

        ready_progress = ProgressBar(
            total_number_of_things_to_do=2,
            string_describing_what_being_progressed=(
                "Waiting for cores to be either in PAUSED or READY state"))

        # wait till all simulation cores are in paused or ready
        txrx.wait_for_cores_to_be_in_state(
            core_subsets, app_id, [CPUState.PAUSED, CPUState.READY],
            error_states=frozenset({
                CPUState.RUN_TIME_EXCEPTION, CPUState.WATCHDOG,
                CPUState.FINISHED}))
        ready_progress.update(1)

        # sort out first run setup
        if current_timestep_map is None:
            current_timestep_map = dict()

        if run_time is None:
            self._set_off_infinite_run(txrx, core_subsets)
            ready_progress.end()
        else:
            subsets_with_same_data = self._determine_true_core_subsets(
                core_subsets, placements, local_machine_time_step_map,
                run_time, current_timestep_map)
            ready_progress.update(1)
            self._set_off_next_step(subsets_with_same_data, txrx)
            ready_progress.end()
        return current_timestep_map
