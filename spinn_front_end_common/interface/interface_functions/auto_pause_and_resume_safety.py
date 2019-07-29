from spinn_front_end_common.abstract_models.\
    abstract_supports_auto_pause_and_resume import \
    AbstractSupportsAutoPauseAndResume
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_utilities.progress_bar import ProgressBar
import numpy
import math

MILLISECONDS_TO_MICROSECONDS = 1000


class AutoPauseAndResumeSafety(object):

    def __call__(
            self, machine_graph, time_scale_factor, machine_time_step,
            runtime):

        # store for all the time periods requested
        time_periods = set()

        progress_bar = ProgressBar(
            len(machine_graph.vertices),
            "checking compatibility of time periods and runtime")

        # locate the unique time periods to link
        for vertex in progress_bar.over(machine_graph.vertices, False):
            if isinstance(vertex, AbstractSupportsAutoPauseAndResume):
                time_periods.add(math.floor(vertex.my_local_time_period(
                    machine_time_step)))

        # determine the lowest common denominator.
        lowest_common_denominator = numpy.lcm.reduce(list(time_periods))
        print("{}".format(lowest_common_denominator))

        # only check combination to runtime if we're not running forever
        if runtime is None:
            return lowest_common_denominator

        # check combination to runtime to see if we can finish at reasonable
        # points
        micro_seconds_of_runtime = runtime * MILLISECONDS_TO_MICROSECONDS
        if micro_seconds_of_runtime % lowest_common_denominator != 0:
            low_cycles = math.floor(
                micro_seconds_of_runtime / lowest_common_denominator)
            high_cycles = math.ceil(
                micro_seconds_of_runtime / lowest_common_denominator)
            low_runtime = (
                (low_cycles * lowest_common_denominator) /
                MILLISECONDS_TO_MICROSECONDS)
            high_runtime = (
                (high_cycles * lowest_common_denominator) /
                MILLISECONDS_TO_MICROSECONDS)

            raise ConfigurationException(
                "Given the time periods of {} requested by the combination "
                "results in a lowest common time step of {}. Unfortunately "
                "this means that the runtime {} cannot be meet correctly. "
                "Please change your runtime to either of these "
                "run times [{}:{}].".format(
                    time_periods, lowest_common_denominator, runtime,
                    low_runtime, high_runtime))

        return lowest_common_denominator








