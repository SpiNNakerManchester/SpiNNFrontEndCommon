from spinn_front_end_common.utilities.utility_objs.extra_monitor_scp_messages.\
    set_router_timeout_message import SetRouterTimeoutMessage
from spinnman.processes.abstract_multi_connection_process \
    import AbstractMultiConnectionProcess


class SetRouterTimeoutProcess(AbstractMultiConnectionProcess):

    def __init__(self, connection_selector):
        AbstractMultiConnectionProcess.__init__(self, connection_selector)

    def set_timeout(self, mantissa, exponent, core_subsets):
        for core_subset in core_subsets.core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(SetRouterTimeoutMessage(
                    core_subset.x, core_subset.y, processor_id,
                    mantissa, exponent))
        self._finish()
        self.check_for_error()
