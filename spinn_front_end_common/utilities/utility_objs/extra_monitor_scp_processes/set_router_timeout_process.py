from spinn_front_end_common.utilities.utility_objs.extra_monitor_scp_messages\
    import SetRouterTimeoutMessage
from spinnman.processes import AbstractMultiConnectionProcess


class SetRouterTimeoutProcess(AbstractMultiConnectionProcess):

    def __init__(self, connection_selector):
        super(SetRouterTimeoutProcess, self).__init__(connection_selector)

    def set_timeout(self, mantissa, exponent, core_subsets, command_code):
        for core_subset in core_subsets.core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(SetRouterTimeoutMessage(
                    core_subset.x, core_subset.y, processor_id,
                    mantissa, exponent, command_code))
        self._finish()
        self.check_for_error()
