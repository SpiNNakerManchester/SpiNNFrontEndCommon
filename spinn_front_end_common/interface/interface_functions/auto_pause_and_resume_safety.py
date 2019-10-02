# Copyright (c) 2019-2020 The University of Manchester
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

from spinn_front_end_common.utilities.constants import \
    MICRO_TO_MILLISECOND_CONVERSION
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_utilities.progress_bar import ProgressBar
import numpy
import math


class AutoPauseAndResumeSafety(object):

    @staticmethod
    def _locate_lowest_common_multiple(time_periods):
        """ code swiped from \
        https://www.geeksforgeeks.org/lcm-of-given-array-elements/
        
        :param time_periods: the list of time periods to find LCM of.
        :return: the LCM of these numbers
        """
        lcm = time_periods[0]
        for i in time_periods[1:]:
            lcm = int(lcm * i / math.gcd(lcm, i))
        return lcm

    def __call__(
            self, machine_graph, time_scale_factor, machine_time_period_map,
            runtime):

        # store for all the time periods requested
        time_periods = set()

        progress_bar = ProgressBar(
            len(machine_time_period_map.keys()),
            "checking compatibility of time periods and runtime")

        # locate the unique time periods to link
        for vertex in progress_bar.over(machine_time_period_map.keys()):
            time_periods.add(machine_time_period_map[vertex])

        # determine the lowest common denominator.
        try:
            lowest_common_multiple = numpy.lcm.reduce(list(time_periods))
        except TypeError:  # if the numpy fails, try the slow way
            lowest_common_multiple = self._locate_lowest_common_multiple(
                list(time_periods))

        # only check combination to runtime if we're not running forever
        if runtime is None:
            return lowest_common_multiple

        # check combination to runtime to see if we can finish at reasonable
        # points
        micro_seconds_of_runtime = runtime * MICRO_TO_MILLISECOND_CONVERSION
        if micro_seconds_of_runtime % lowest_common_multiple != 0:
            low_cycles = math.floor(
                micro_seconds_of_runtime / lowest_common_multiple)
            high_cycles = math.ceil(
                micro_seconds_of_runtime / lowest_common_multiple)
            low_runtime = (
                (low_cycles * lowest_common_multiple) /
                MICRO_TO_MILLISECOND_CONVERSION)
            high_runtime = (
                (high_cycles * lowest_common_multiple) /
                MICRO_TO_MILLISECOND_CONVERSION)

            raise ConfigurationException(
                "Given the time periods of {} requested by the combination "
                "results in a lowest common time step of {}. Unfortunately "
                "this means that the runtime {} cannot be meet correctly. "
                "Please change your runtime to either of these "
                "run times [{}:{}].".format(
                    time_periods, lowest_common_multiple, runtime,
                    low_runtime, high_runtime))

        return lowest_common_multiple
