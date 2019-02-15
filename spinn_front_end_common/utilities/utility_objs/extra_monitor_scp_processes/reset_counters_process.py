from spinn_front_end_common.utilities.utility_objs.extra_monitor_scp_messages\
    import (
        ResetCountersMessage)
from spinnman.processes import AbstractMultiConnectionProcess


class ResetCountersProcess(AbstractMultiConnectionProcess):
    def __init__(self, connection_selector):
        super(ResetCountersProcess, self).__init__(connection_selector)

    def reset_counters(self, core_subsets):
        for core_subset in core_subsets.core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(ResetCountersMessage(
                    core_subset.x, core_subset.y, processor_id))
        self._finish()
        self.check_for_error()
