from spinn_front_end_common.utilities.utility_objs.extra_monitor_scp_messages\
    import (
        SetRouterEmergencyTimeoutMessage)
from spinnman.processes import AbstractMultiConnectionProcess


class SetRouterEmergencyTimeoutProcess(AbstractMultiConnectionProcess):
    def __init__(self, connection_selector):
        super(SetRouterEmergencyTimeoutProcess, self).__init__(
            connection_selector)

    def set_timeout(self, mantissa, exponent, core_subsets):
        for core in core_subsets.core_subsets:
            for processor_id in core.processor_ids:
                self._set_timeout(core, processor_id, mantissa, exponent)

    def _set_timeout(self, core, processor_id, mantissa, exponent):
        self._send_request(SetRouterEmergencyTimeoutMessage(
            core.x, core.y, processor_id, mantissa, exponent))
        self._finish()
        self.check_for_error()
