from spinn_front_end_common.utilities.constants import \
    MICRO_TO_MILLISECOND_CONVERSION
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_utilities.progress_bar import ProgressBar
import numpy
import math


class AutoPauseAndResumeSafety(object):

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
        lowest_common_multiple = numpy.lcm.reduce(list(time_periods))
        print("{}".format(lowest_common_multiple))

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
