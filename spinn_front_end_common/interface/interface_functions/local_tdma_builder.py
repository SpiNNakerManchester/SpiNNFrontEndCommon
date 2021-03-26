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
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.abstract_models.impl.\
    tdma_aware_application_vertex import (
        TDMAAwareApplicationVertex)
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.helpful_functions import (
    read_config_int, read_config_float)
from spinn_front_end_common.utilities.globals_variables import get_simulator
from spinn_front_end_common.utilities.constants import CLOCKS_PER_US

logger = FormatAdapter(logging.getLogger(__name__))


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

    # default fraction of the real time we will use for spike transmissions
    FRACTION_OF_TIME_FOR_SPIKE_SENDING = 0.8
    FRACTION_OF_TIME_STEP_BEFORE_SPIKE_SENDING = 0.1

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
        us_per_cycle = int(math.ceil(machine_time_step * time_scale_factor))
        clocks_per_cycle = us_per_cycle * CLOCKS_PER_US
        (app_machine_quantity, clocks_between_cores, clocks_for_sending,
         clocks_waiting, clocks_initial) = self.config_values(clocks_per_cycle)

        # calculate for each app vertex if the time needed fits
        app_verts = list()
        max_fraction_of_sending = 0
        for app_vertex in application_graph.vertices:
            if isinstance(app_vertex, TDMAAwareApplicationVertex):
                app_verts.append(app_vertex)

                # get timings

                # check config params for better performance
                (n_at_same_time, local_clocks) = self._auto_config_times(
                    app_machine_quantity, clocks_between_cores,
                    clocks_for_sending, app_vertex, n_keys_map,
                    machine_graph, clocks_waiting)
                n_phases, n_slots, clocks_between_phases = \
                    self._generate_times(
                        machine_graph, app_vertex, n_at_same_time,
                        local_clocks, n_keys_map)

                # store in tracker
                app_vertex.set_other_timings(
                    local_clocks, n_slots, clocks_between_phases,
                    n_phases, clocks_per_cycle)

                # test timings
                fraction_of_sending = self._get_fraction_of_sending(
                    n_phases, clocks_between_phases, clocks_for_sending)
                if fraction_of_sending is not None:
                    max_fraction_of_sending = max(
                        max_fraction_of_sending, fraction_of_sending)

        time_scale_factor_needed = time_scale_factor * max_fraction_of_sending
        if max_fraction_of_sending > 1:
            logger.warning(
                "A time scale factor of {} may be needed to run correctly"
                .format(time_scale_factor_needed))
        elif max_fraction_of_sending < 1:
            logger.info(
                "The time scale factor could be reduced to {}"
                .format(time_scale_factor_needed))

        # get initial offset for each app vertex.
        for app_vertex in application_graph.vertices:
            if isinstance(app_vertex, TDMAAwareApplicationVertex):
                initial_offset = self._generate_initial_offset(
                    app_vertex, app_verts, clocks_initial,
                    clocks_waiting)
                app_vertex.set_initial_offset(initial_offset)

    @staticmethod
    def _auto_config_times(
            app_machine_quantity, clocks_between_cores, clocks_for_sending,
            app_vertex, n_keys_map, machine_graph, clocks_waiting):

        n_cores = app_vertex.get_n_cores()
        n_phases = app_vertex.find_n_phases_for(machine_graph, n_keys_map)

        # If there are no packets sent, pretend there is 1 to avoid division
        # by 0; it won't actually matter anyway
        if n_phases == 0:
            n_phases = 1

        # Overall time of the TDMA window minus initial offset
        overall_clocks_available = clocks_for_sending - clocks_waiting

        # Easier bool compares
        core_set = clocks_between_cores is not None
        app_set = app_machine_quantity is not None

        # Adjust time between cores to fit time scale
        if not core_set and app_set:
            n_slots = int(math.ceil(n_cores / app_machine_quantity))
            clocks_per_phase = (
                int(math.ceil(overall_clocks_available / n_phases)))
            # Note: The plus 1 ensures the last core finishes, if it's the
            # worst in terms of n keys to transmit
            clocks_between_cores = clocks_per_phase / (n_slots + 1)
            logger.debug("adjusted clocks between cores is {}".format(
                clocks_between_cores))

        # Adjust cores at same time to fit time between cores.
        if core_set and not app_set:
            clocks_per_phase = (
                int(math.ceil(overall_clocks_available / n_phases)))
            max_slots = int(math.floor(
                clocks_per_phase / clocks_between_cores))
            app_machine_quantity = int(math.ceil(n_cores / max_slots))
            logger.debug(
                "Adjusted the number of cores of a app vertex that "
                "can fire at the same time to {}".format(
                    app_machine_quantity))

        return app_machine_quantity, clocks_between_cores

    @staticmethod
    def _generate_initial_offset(
            app_vertex, app_verts, clocks_between_cores, clocks_waiting):
        """ Calculates from the app vertex index the initial offset for the\
            TDMA between all cores

        :param ~pacman.model.graphs.application.ApplicationVertex app_vertex:
            the app vertex in question.
        :param app_verts: the list of app vertices.
        :type app_verts:
            list(~pacman.model.graphs.application.ApplicationVertex)
        :param int clocks_between_cores: the clock cycles between cores.
        :param int clocks_waiting: the clock cycles to wait for.
        :return: the initial offset for this app vertex including wait time.
        :rtype: int
        """
        # This is an offset between cores
        initial_offset_clocks = int(math.ceil(
            (app_verts.index(app_vertex) * clocks_between_cores) /
            len(app_verts)))
        # add the offset the clocks to wait for before sending anything at all
        initial_offset_clocks += clocks_waiting
        return initial_offset_clocks

    @staticmethod
    def _generate_times(
            machine_graph, app_vertex, app_machine_quantity,
            clocks_between_cores, n_keys_map):
        """ Generates the number of phases needed for this app vertex, as well\
            as the number of slots and the time between spikes for this app\
            vertex, given the number of machine verts to fire at the same time\
            from a given app vertex.

        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
            machine graph
        :param TDMAAwareApplicationVertex app_vertex: the app vertex
        :param int app_machine_quantity: the pop spike control level
        :param int clocks_between_cores: the clock cycles between cores
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
        clocks_between_phases = int(math.ceil(clocks_between_cores * n_slots))

        return n_phases, n_slots, clocks_between_phases

    def _get_fraction_of_sending(
            self, n_phases, clocks_between_phases, clocks_for_sending):
        """ Get the fraction of the send

        :param int n_phases:
            the max number of phases this TDMA needs for a given app vertex
        :param int time_between_phases: the time between phases.
        :param float fraction_of_sending:
            fraction of time step for sending packets
        :param str label: the app vertex we're considering at this point
        :return:
        """

        # figure how much time this TDMA needs
        total_clocks_needed = n_phases * clocks_between_phases
        return total_clocks_needed / clocks_for_sending

    def __check_at_most_one(self, name_1, value_1, name_2, value_2):
        if value_1 is not None and value_2 is not None:
            raise ConfigurationException(
                "Both {} and {} have been specified; please choose just one"
                .format(name_1, name_2))

    def __check_only_one(self, name_1, value_1, name_2, value_2):
        """ Checks that exactly one of the values is not None
        """
        self.__check_at_most_one(name_1, value_1, name_2, value_2)
        if value_1 is None and value_2 is None:
            raise ConfigurationException(
                "Exactly one of {} and {} must be specified".format(
                    name_1, name_2))

    def config_values(self, clocks_per_cycle):
        """ Read the config for the right parameters and combinations.

        :param int clocks_per_cycle: The number of clock cycles per time step
        :return: (app_machine_quantity, clocks_between_cores,
                clocks_for_sending, clocks_waiting, initial_clocks)
        :rtype: tuple(int, int, int, int. int)
        """

        # get config
        config = get_simulator().config

        # set the number of cores expected to fire at any given time
        app_machine_quantity = read_config_int(
            config, "Simulation", "app_machine_quantity")

        # set the time between cores to fire
        time_between_cores = read_config_float(
            config, "Simulation", "time_between_cores")
        clocks_between_cores = read_config_int(
            config, "Simulation", "clock_cycles_between_cores")
        self.__check_at_most_one(
            "time_between_cores", time_between_cores,
            "clock_cycles_betwen_cores", clocks_between_cores)
        if (time_between_cores is None and clocks_between_cores is None and
                app_machine_quantity is None):
            raise ConfigurationException(
                "Either one of time_between_cores and clocks_between_cores"
                " must be specified or else app_machine_quantity must be"
                " specified")
        if time_between_cores is not None:
            clocks_between_cores = time_between_cores * CLOCKS_PER_US

        # time spend sending
        fraction_of_sending = read_config_float(
            config, "Simulation", "fraction_of_time_spike_sending")
        clocks_for_sending = read_config_int(
            config, "Simulation", "clock_cycles_sending")
        self.__check_only_one(
            "fraction_of_time_spike_sending", fraction_of_sending,
            "clock_cycles_sending", clocks_for_sending)
        if fraction_of_sending is not None:
            clocks_for_sending = int(round(
                clocks_per_cycle * fraction_of_sending))

        # time waiting before sending
        fraction_of_waiting = read_config_float(
            config, "Simulation", "fraction_of_time_before_sending")
        clocks_waiting = read_config_int(
            config, "Simulation", "clock_cycles_before_sending")
        self.__check_only_one(
            "fraction_of_time_before_sending", fraction_of_waiting,
            "clock_cycles_before_sending", clocks_waiting)
        if fraction_of_waiting is not None:
            clocks_waiting = int(round(clocks_per_cycle * fraction_of_waiting))

        # time to offset app vertices between each other
        fraction_initial = read_config_float(
            config, "Simulation", "fraction_of_time_for_offset")
        clocks_initial = read_config_int(
            config, "Simulation", "clock_cycles_for_offset")
        self.__check_only_one(
            "fraction_of_time_for_offset", fraction_initial,
            "clock_cycles_for_offset", clocks_initial)
        if fraction_initial is not None:
            clocks_initial = int(round(clocks_per_cycle * fraction_initial))

        # check fractions less than 1.
        if (clocks_for_sending + clocks_waiting + clocks_initial >
                clocks_per_cycle):
            raise ConfigurationException(
                "The total time for the TDMA must not exceed the time per"
                " cycle")

        return (app_machine_quantity, clocks_between_cores,
                clocks_for_sending, clocks_waiting, clocks_initial)
