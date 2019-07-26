from spinn_front_end_common.abstract_models.\
    abstract_supports_auto_pause_and_resume import \
    AbstractSupportsAutoPauseAndResume


class SupportsAutoPauseAndResume(AbstractSupportsAutoPauseAndResume):

    def my_local_time_period(self, simulator_time_step, time_scale_factor):
        return simulator_time_step * time_scale_factor