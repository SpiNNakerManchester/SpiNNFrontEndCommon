# Copyright (c) 2020-2021 The University of Manchester
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

import logging
import math
from spinn_utilities.logger_utils import warn_once
from spinn_front_end_common.abstract_models.impl.\
    tdma_aware_application_vertex import (
        TDMAAwareApplicationVertex)
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.helpful_functions import (
    read_config_int, read_config_float, read_config)
from spinn_front_end_common.utilities.globals_variables import get_simulator

logger = logging.getLogger(__name__)


class LocalTDMABuilder(object):
    """ Builds a localised TDMA which allows a number of machine vertices
    of the same application vertex to fire at the same time. Ensures that
    other application vertices are not firing at the same time. Verifies if
    the total time required fits into the time scale factor and machine time
    step. Below are text diagrams to show how this works in principle.

    *Figure 1:* bits needed to figure out time between spikes.
    Cores 0-4 have 2 atoms, core 5 has 1 atom::

        #        0     1       2      3       4      5
        # T2-[   X                    X
        #    |         X                      X
        #    |                 X                     X
        #    [  X                     X
        #       |------| T
        #              X                      X
        #                      X <- T3

        T = time_between_cores
        T2 = time_between_phases
        T3 = end of TDMA (equiv of ((n_phases + 1) * T2))
        cutoff = 2. n_phases = 3 max_atoms = 2

    Constants etc just to get into head:

    * clock cycles = 200 Mhz = 200 = sv->cpu_clk
    * 1ms = 200000 for timer 1. = clock cycles
    * 200 per microsecond
    * machine time step = microseconds already.
    * `__time_between_cores` = microseconds.

    *Figure 2:* initial offset (used to try to interleave packets from other
    app verts into the TDMA without extending the overall time, and
    trying to stop multiple packets in flight at same time).

    *Figure 3:* bits needed to figure out time between spikes.
    Cores 0-4 have 2 atoms, core 5 has 1 atom::

        #        0  .5   1   .5    2   .5   3    .5   4   .5   5  .5
        # T2-[   X   Y                      X     Y
        #    |           X   Y                        X    Y
        #    |                     X    Y                      X   Y
        #    [  X    Y                      X     Y
        #       |-------| T
        #               X    Y                        X    Y
        #               |----| T4
        #                   T3 ->  X    Y

        T4 is the spreader between populations.
        X is pop0 firing,
        Y is pop1 firing
    """

    # error message for when the vertex TDMA isnt feasible.
    _VERTEX_TDMA_FAILURE_MSG = (
        "vertex {} does not have enough time to execute the "
        "TDMA in the given time. The population would need a time "
        "scale factor of {} to correctly execute this TDMA.")

    # default fraction of the real time we will use for spike transmissions
    FRACTION_OF_TIME_FOR_SPIKE_SENDING = 0.8
    FRACTION_OF_TIME_STEP_BEFORE_SPIKE_SENDING = 0.1

    # default number of cores to fire at same time from this population
    _DEFAULT_N_CORES_AT_SAME_TIME = 7

    # default number of microseconds between cores firing
    _DEFAULT_TIME_BETWEEN_CORES = 50

    def __call__(
            self, machine_graph, machine_time_step, time_scale_factor,
            n_keys_map, application_graph=None):
        """ main entrance

        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
            machine graph.
        :param int machine_time_step: the machine time step.
        :param int time_scale_factor: the time scale factor.
        :param n_keys_map: the map of partitions to n keys.
        :type n_keys_map:
            ~pacman.model.routing_info.AbstractMachinePartitionNKeysMap
        :param application_graph: app graph.
        :type application_graph:
            ~pacman.model.graphs.application.ApplicationGraph or None
        """
        if application_graph is None:
            return

        # get config params
        (app_machine_quantity, time_between_cores,
         fraction_of_sending, fraction_of_waiting) = self.config_values()

        # calculate for each app vertex if the time needed fits
        app_verts = list()
        for app_vertex in application_graph.vertices:
            if isinstance(app_vertex, TDMAAwareApplicationVertex):
                app_verts.append(app_vertex)

                # get timings
                n_phases, n_slots, time_between_phases = self._generate_times(
                    machine_graph, app_vertex, app_machine_quantity,
                    time_between_cores, n_keys_map)

                # store in tracker
                app_vertex.set_other_timings(
                    time_between_cores, n_slots, time_between_phases, n_phases,
                    int(math.ceil(machine_time_step * time_scale_factor)))

                # test timings
                self._test_timings(
                    n_phases, time_between_phases, machine_time_step,
                    time_scale_factor, fraction_of_sending, app_vertex.label)

        # get initial offset for each app vertex.
        for app_vertex in application_graph.vertices:
            if isinstance(app_vertex, TDMAAwareApplicationVertex):
                initial_offset = self._generate_initial_offset(
                    app_vertex, app_verts, time_between_cores,
                    machine_time_step, time_scale_factor, fraction_of_waiting)
                app_vertex.set_initial_offset(initial_offset)

    @staticmethod
    def _generate_initial_offset(
            app_vertex, app_verts, time_between_cores,
            machine_time_step, time_scale_factor, fraction_of_waiting):
        """ figures from the app vertex index the initial offset.

        :param ~pacman.model.graphs.application.ApplicationVertex app_vertex:
            the app vertex in question.
        :param app_verts: the list of app vertices.
        :type app_verts:
            list(~pacman.model.graphs.application.ApplicationVertex)
        :param int time_between_cores: the time between cores.
        :param int machine_time_step: the machine time step.
        :param int time_scale_factor: the time scale factor.
        :param float fraction_of_waiting: the fraction of time for waiting.
        :return: the initial offset for this app vertex.
        :rtype: int
        """

        initial_offset = app_verts.index(app_vertex) * int(
            math.ceil(len(app_verts) / time_between_cores))
        # add the offset of a portion of the time step BEFORE doing any
        # slots to allow initial processing to work.
        initial_offset += int(math.ceil(
            (machine_time_step * time_scale_factor) * fraction_of_waiting))
        return initial_offset

    @staticmethod
    def _generate_times(
            machine_graph, app_vertex, app_machine_quantity,
            time_between_cores, n_keys_map):
        """ Generates the number of phases needed for this app vertex, as well\
            as the number of slots and the time between spikes for this app\
            vertex, given the number of machine verts to fire at the same time\
            from a given app vertex.

        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
            machine graph
        :param TDMAAwareApplicationVertex app_vertex: the app vertex
        :param int app_machine_quantity: the pop spike control level
        :param float time_between_cores: the time between cores
        :param n_keys_map: the partition to n keys map.
        :type n_keys_map:
            ~pacman.model.routing_info.AbstractMachinePartitionNKeysMap
        :return: (n_phases, n_slots, time_between_phases) for this app vertex
        :rtype: tuple(int, int, int)
        """

        # Figure total T2s
        n_phases = app_vertex.find_n_phases_for(machine_graph, n_keys_map)

        # how many hops between T2's
        n_cores = app_vertex.get_n_cores()
        n_slots = int(math.ceil(n_cores / app_machine_quantity))

        # figure T2
        time_between_phases = int(math.ceil(time_between_cores * n_slots))

        return n_phases, n_slots, time_between_phases

    def _test_timings(
            self, n_phases, time_between_phases, machine_time_step,
            time_scale_factor, fraction_of_sending, label):
        """ verifies that the timings fit into the time scale factor and \
            machine time step.

        :param int n_phases:
            the max number of phases this TDMA needs for a given app vertex
        :param int time_between_phases: the time between phases.
        :param int machine_time_step: the machine time step
        :param int time_scale_factor: the time scale factor
        :param float fraction_of_sending:
            fraction of time step for sending packets
        :param str label: the app vertex we're considering at this point
        :return:
        """

        # figure how much time this TDMA needs
        total_time_needed = n_phases * time_between_phases

        # figure how much time the TDMA has in transmission
        total_time_available = int(math.ceil(
            machine_time_step * time_scale_factor * fraction_of_sending))
        if total_time_needed > total_time_available:
            time_scale_factor_needed = math.ceil(
                total_time_needed / machine_time_step / fraction_of_sending)
            msg = self._VERTEX_TDMA_FAILURE_MSG.format(
                label, time_scale_factor_needed)
            logger.warning(msg)
        if total_time_needed != 0:
            # maybe this warn could be thrown away?
            true_fraction = 1 / (
                machine_time_step * time_scale_factor / total_time_needed)
            warn_once(
                logger,
                "could reduce fraction of time for sending to {}".format(
                    true_fraction))

    def config_values(self):
        """ read the config for the right params. Check the 2 fractions are \
            together less than 1. else broken

        :return: (app_machine_quantity, time_between_cores,
                fraction_of_sending, fraction_of_waiting)
        :rtype: tuple(int, float, float, float)
        """

        # get config
        config = get_simulator().config

        # set the number of cores expected to fire at any given time
        app_machine_quantity = read_config_int(
            config, "Simulation", "app_machine_quantity")
        if app_machine_quantity is None:
            app_machine_quantity = self._DEFAULT_N_CORES_AT_SAME_TIME

        # set the time between cores to fire
        time_between_cores = read_config_float(
            config, "Simulation", "time_between_cores")
        if time_between_cores is None:
            time_between_cores = self._DEFAULT_TIME_BETWEEN_CORES

        # fraction of time spend sending
        fraction_of_sending = read_config(
            config, "Simulation", "fraction_of_time_spike_sending")
        if fraction_of_sending is None:
            fraction_of_sending = (
                self.FRACTION_OF_TIME_FOR_SPIKE_SENDING)
        else:
            fraction_of_sending = float(fraction_of_sending)

        # fraction of time waiting before sending
        fraction_of_waiting = read_config(
            config, "Simulation", "fraction_of_time_before_sending")
        if fraction_of_waiting is None:
            fraction_of_waiting = (
                self.FRACTION_OF_TIME_STEP_BEFORE_SPIKE_SENDING)
        else:
            fraction_of_waiting = float(fraction_of_waiting)

        # check fractions less than 1.
        if fraction_of_sending + fraction_of_waiting > 1:
            raise ConfigurationException(
                "the 2 fractions of timing need to be at most 1.")

        return (app_machine_quantity, time_between_cores,
                fraction_of_sending, fraction_of_waiting)
