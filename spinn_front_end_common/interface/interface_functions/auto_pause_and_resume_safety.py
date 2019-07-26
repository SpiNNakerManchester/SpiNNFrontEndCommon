from spinn_front_end_common.abstract_models.\
    abstract_supports_auto_pause_and_resume import \
    AbstractSupportsAutoPauseAndResume
from spinn_utilities.progress_bar import ProgressBar
import numpy


class AutoPauseAndResumeSafety(object):

    def __call__(
            self, machine_graph, time_scale_factor, machine_time_step,
            runtime):

        time_periods = set()

        progress_bar = ProgressBar(
            len(machine_graph.vertices) * 2,
            "checking compatibility of time periods and runtime")

        for vertex in progress_bar.over(machine_graph.vertices, False):
            if isinstance(vertex, AbstractSupportsAutoPauseAndResume):
                time_periods.add(vertex.my_local_time_period(
                    machine_time_step, time_scale_factor))

        lowest_common_denominator = numpy.lcm.reduce(time_periods)
        print("aaaa")

