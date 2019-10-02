from spinn_front_end_common.abstract_models.\
    abstract_application_supports_auto_pause_and_resume import \
    AbstractApplicationSupportsAutoPauseAndResume
from spinn_utilities.overrides import overrides


class ApplicationSupportsAutoPauseAndResume(
        AbstractApplicationSupportsAutoPauseAndResume):

    @overrides(
        AbstractApplicationSupportsAutoPauseAndResume.
        my_variable_local_time_period)
    def my_variable_local_time_period(
            self, default_machine_time_step, variable):
        return default_machine_time_step
