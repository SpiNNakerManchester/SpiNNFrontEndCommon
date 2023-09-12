# Copyright (c) 2020 The University of Manchester
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

import logging
import math
from typing import Any, Optional, Tuple
from spinn_utilities.log import FormatAdapter
from spinn_utilities.config_holder import (
    get_config_float_or_none, get_config_int, get_config_int_or_none)
from spinn_front_end_common.abstract_models.impl.\
    tdma_aware_application_vertex import (
        TDMAAwareApplicationVertex)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.constants import CLOCKS_PER_US
logger = FormatAdapter(logging.getLogger(__name__))

# default fraction of the real time we will use for spike transmissions
FRACTION_OF_TIME_FOR_SPIKE_SENDING = 0.8
FRACTION_OF_TIME_STEP_BEFORE_SPIKE_SENDING = 0.1


def local_tdma_builder() -> None:
    """
    Builds a localised TDMA.

    Builds a localised TDMA which allows a number of machine vertices
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

    * clock cycles = 200 MHz = 200 = sv->cpu_clk
    * 1ms = 200000 for timer 1. = clock cycles
    * 200 per microsecond
    * machine time step = microseconds already.
    * `__time_between_cores` = microseconds.

    *Figure 2:* initial offset (used to try to interleave packets from other
    application vertices into the TDMA without extending the overall time, and
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
    if FecDataView.get_n_vertices() == 0:
        return
    # get config params
    us_per_cycle = FecDataView.get_hardware_time_step_us()
    clocks_per_cycle = us_per_cycle * CLOCKS_PER_US
    (app_machine_quantity, clocks_between_cores, clocks_for_sending,
     clocks_waiting, clocks_initial) = __config_values(clocks_per_cycle)

    # calculate for each app vertex if the time needed fits
    app_verts = list(FecDataView.get_vertices_by_type(
        TDMAAwareApplicationVertex))
    max_fraction_of_sending = 0.0
    for app_vertex in app_verts:
        # get timings

        # check config params for better performance
        n_at_same_time, local_clocks = __auto_config_times(
            app_machine_quantity, clocks_between_cores,
            clocks_for_sending, app_vertex, clocks_waiting)
        n_phases, n_slots, clocks_between_phases = __generate_times(
            app_vertex, n_at_same_time, local_clocks)

        # store in tracker
        app_vertex.set_other_timings(
            local_clocks, n_slots, clocks_between_phases,
            n_phases, clocks_per_cycle)

        # test timings
        max_fraction_of_sending = max(
            max_fraction_of_sending, __get_fraction_of_sending(
                n_phases, clocks_between_phases, clocks_for_sending))

    time_scale_factor_needed = (
        FecDataView.get_time_scale_factor() * max_fraction_of_sending)
    if max_fraction_of_sending > 1.0:
        logger.warning(
            "A time scale factor of {} may be needed to run correctly",
            time_scale_factor_needed)

    # get initial offset for each app vertex.
    for index, app_vertex in enumerate(app_verts):
        app_vertex.set_initial_offset(__generate_initial_offset(
            index, len(app_verts), clocks_initial, clocks_waiting))


def __auto_config_times(
        app_machine_quantity: Optional[int],
        clocks_between_cores: Optional[int], clocks_for_sending: int,
        app_vertex: TDMAAwareApplicationVertex, clocks_waiting: int) -> Tuple[
            int, int]:
    n_cores = app_vertex.get_n_cores()
    n_phases = app_vertex.get_n_phases()

    # If there are no packets sent, pretend there is 1 to avoid division
    # by 0; it won't actually matter anyway
    if n_phases == 0:
        n_phases = 1

    # Overall time of the TDMA window minus initial offset
    overall_clocks_available = clocks_for_sending - clocks_waiting

    if clocks_between_cores is None:
        if app_machine_quantity is None:
            raise ConfigurationException("impossible TDMA configuration")
        # Adjust time between cores to fit time scale
        n_slots = int(math.ceil(n_cores / app_machine_quantity))
        clocks_per_phase = int(math.ceil(
            overall_clocks_available / n_phases))
        clocks_between_cores = int(clocks_per_phase / n_slots)
        logger.debug(
            "adjusted clocks between cores is {}",
            clocks_between_cores)
        return app_machine_quantity, clocks_between_cores
    else:
        if app_machine_quantity is not None:
            return app_machine_quantity, clocks_between_cores
        # Adjust cores at same time to fit time between cores.
        clocks_per_phase = int(math.ceil(
            overall_clocks_available / n_phases))
        max_slots = int(clocks_per_phase // clocks_between_cores)
        app_machine_quantity = int(math.ceil(n_cores / max_slots))
        logger.debug(
            "Adjusted the number of cores of a app vertex that "
            "can fire at the same time to {}",
            app_machine_quantity)
        return app_machine_quantity, clocks_between_cores


def __generate_initial_offset(
        index: int, length: int, clocks_between_cores: int,
        clocks_waiting: int) -> int:
    """
    Calculates from the app vertex index the initial offset for the
    TDMA between all cores.

    :param int index:
        the index of the app vertex in question.
    :param int length:
        the total number of of app vertices.
    :param int clocks_between_cores: the clock cycles between cores.
    :param int clocks_waiting: the clock cycles to wait for.
    :return: the initial offset for this app vertex including wait time.
    :rtype: int
    """
    # This is an offset between cores
    initial_offset_clocks = int(math.ceil(
        (index * clocks_between_cores) / length))
    # add the offset the clocks to wait for before sending anything at all
    initial_offset_clocks += clocks_waiting
    return initial_offset_clocks


def __generate_times(
        app_vertex: TDMAAwareApplicationVertex, app_machine_quantity: int,
        clocks_between_cores: int) -> Tuple[int, int, int]:
    """
    Generates the number of phases needed for this app vertex, as well as the
    number of slots and the time between spikes for this app vertex, given the
    number of machine verts to fire at the same time from a given app vertex.

    :param TDMAAwareApplicationVertex app_vertex: the app vertex
    :param int app_machine_quantity: the pop spike control level
    :param int clocks_between_cores: the clock cycles between cores
    :return: (n_phases, n_slots, time_between_phases) for this app vertex
    :rtype: tuple(int, int, int)
    """
    # Figure total T2s
    n_phases = app_vertex.get_n_phases()

    # how many hops between T2's
    n_cores = app_vertex.get_n_cores()
    n_slots = int(math.ceil(n_cores / app_machine_quantity))

    # figure T2
    clocks_between_phases = int(math.ceil(clocks_between_cores * n_slots))

    return n_phases, n_slots, clocks_between_phases


def __get_fraction_of_sending(
        n_phases: int, clocks_between_phases: int,
        clocks_for_sending: int) -> float:
    """
    Get the fraction of the send.

    :param int n_phases:
        the max number of phases this TDMA needs for a given app vertex
    :param int clocks_between_phases: the time between phases, in clocks.
    :param int clocks_for_sending: the time to do a send, in clocks
    :rtype: float
    """
    # figure how much time this TDMA needs
    total_clocks_needed = n_phases * clocks_between_phases
    return total_clocks_needed / clocks_for_sending


def __check_at_most_one(name_1: str, value_1: Any, name_2: str, value_2: Any):
    if value_1 is not None and value_2 is not None:
        raise ConfigurationException(
            f"Both {name_1} and {name_2} have been specified; "
            "please choose just one")


def __check_only_one(name_1: str, value_1: Any, name_2: str, value_2: Any):
    """
    Checks that exactly one of the values is not `None`.
    """
    __check_at_most_one(name_1, value_1, name_2, value_2)
    if value_1 is None and value_2 is None:
        raise ConfigurationException(
            f"Exactly one of {name_1} and {name_2} must be specified")


def __config_values(clocks_per_cycle: int) -> Tuple[
        Optional[int], Optional[int], int, int, int]:
    """
    Read the configuration for the right parameters and combinations.

    :param int clocks_per_cycle: The number of clock cycles per time step
    :return: (app_machine_quantity, clocks_between_cores,
            clocks_for_sending, clocks_waiting, initial_clocks)
    :rtype: tuple(int, int, int, int. int)
    """
    # set the number of cores expected to fire at any given time
    app_machine_quantity = get_config_int(
        "Simulation", "app_machine_quantity")

    # set the time between cores to fire
    time_between_cores = get_config_float_or_none(
        "Simulation", "time_between_cores")
    clocks_between_cores = get_config_int_or_none(
        "Simulation", "clock_cycles_between_cores")
    __check_at_most_one(
        "time_between_cores", time_between_cores,
        "clock_cycles_betwen_cores", clocks_between_cores)
    if time_between_cores is not None:
        if clocks_between_cores is None:
            clocks_between_cores = int(time_between_cores * CLOCKS_PER_US)
        else:
            raise ConfigurationException(
                "Only one of time_between_cores and clocks_between_cores"
                " may be specified")

    # time spend sending
    fraction_of_sending = get_config_float_or_none(
        "Simulation", "fraction_of_time_spike_sending")
    clocks_for_sending = get_config_int_or_none(
        "Simulation", "clock_cycles_sending")
    __check_only_one(
        "fraction_of_time_spike_sending", fraction_of_sending,
        "clock_cycles_sending", clocks_for_sending)
    if fraction_of_sending is not None:
        clocks_for_sending = int(round(
            clocks_per_cycle * fraction_of_sending))
    assert clocks_for_sending is not None

    # time waiting before sending
    fraction_of_waiting = get_config_float_or_none(
        "Simulation", "fraction_of_time_before_sending")
    clocks_waiting = get_config_int(
        "Simulation", "clock_cycles_before_sending")
    __check_only_one(
        "fraction_of_time_before_sending", fraction_of_waiting,
        "clock_cycles_before_sending", clocks_waiting)
    if fraction_of_waiting is not None:
        clocks_waiting = int(round(clocks_per_cycle * fraction_of_waiting))

    # time to offset app vertices between each other
    fraction_initial = get_config_float_or_none(
        "Simulation", "fraction_of_time_for_offset")
    clocks_initial = get_config_int_or_none(
        "Simulation", "clock_cycles_for_offset")
    __check_only_one(
        "fraction_of_time_for_offset", fraction_initial,
        "clock_cycles_for_offset", clocks_initial)
    if fraction_initial is not None:
        clocks_initial = int(round(clocks_per_cycle * fraction_initial))
    elif clocks_initial is None:
        clocks_initial = 1000

    # check fractions less than 1.
    if (clocks_for_sending + clocks_waiting + clocks_initial >
            clocks_per_cycle):
        raise ConfigurationException(
            "The total time for the TDMA must not exceed the time per"
            " cycle")

    return (app_machine_quantity, clocks_between_cores,
            clocks_for_sending, clocks_waiting, clocks_initial)
