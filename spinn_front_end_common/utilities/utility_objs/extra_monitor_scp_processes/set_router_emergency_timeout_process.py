from spinn_front_end_common.utilities.utility_objs.extra_monitor_scp_messages.\
    set_router_emergency_timeout_message import \
    SetRouterEmergencyTimeoutMessage
from spinnman.processes.abstract_multi_connection_process \
    import AbstractMultiConnectionProcess


class SetRouterEmergencyTimeoutProcess(AbstractMultiConnectionProcess):
    def __init__(self, connection_selector):
        AbstractMultiConnectionProcess.__init__(self, connection_selector)

    def set_timeout(self, mantissa, exponent, core_subsets, command_code):
        for core_subset in core_subsets.core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(SetRouterEmergencyTimeoutMessage(
                    core_subset.x, core_subset.y, processor_id,
                    mantissa, exponent, command_code))
        self._finish()
        self.check_for_error()
