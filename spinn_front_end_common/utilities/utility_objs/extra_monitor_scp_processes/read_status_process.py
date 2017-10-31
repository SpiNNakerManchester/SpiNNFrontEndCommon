from spinn_front_end_common.utilities.utility_objs.\
    extra_monitor_scp_messages.get_reinjection_status_message import \
    GetReinjectionStatusMessage
from spinnman.processes.abstract_multi_connection_process import \
    AbstractMultiConnectionProcess


class ReadStatusProcess(AbstractMultiConnectionProcess):
    def __init__(self, connection_selector):
        AbstractMultiConnectionProcess.__init__(self, connection_selector)
        self._reinjector_status = dict()

    def handle_reinjection_status_response(self, response):
        status = response.reinjection_functionality_status
        self._reinjector_status[(response.sdp_header.source_chip_x,
                                 response.sdp_header.source_chip_y)] = status

    def get_reinjection_status(self, x, y, p, command_code):
        self._reinjector_status = dict()
        self._send_request(GetReinjectionStatusMessage(x, y, p, command_code),
                           callback=self.handle_reinjection_status_response)
        self._finish()
        self.check_for_error()
        return self._reinjector_status[(x, y)]

    def get_reinjection_status_for_core_subsets(
            self, core_subsets, command_code):
        self._reinjector_status = dict()
        for core_subset in core_subsets.core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(GetReinjectionStatusMessage(
                    core_subset.x, core_subset.y, processor_id, command_code),
                    callback=self.handle_reinjection_status_response)
        self._finish()
        self.check_for_error()
        return self._reinjector_status

