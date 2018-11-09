from spinn_front_end_common.utilities.utility_objs.extra_monitor_scp_messages\
    import (
        GetReinjectionStatusMessage)
from spinnman.processes import AbstractMultiConnectionProcess


class ReadStatusProcess(AbstractMultiConnectionProcess):
    def __init__(self, connection_selector):
        super(ReadStatusProcess, self).__init__(connection_selector)
        self._reinjection_status = dict()

    def handle_reinjection_status_response(self, response):
        status = response.reinjection_functionality_status
        self._reinjection_status[(response.sdp_header.source_chip_x,
                                  response.sdp_header.source_chip_y)] = status

    def get_reinjection_status(self, x, y, p):
        self._reinjection_status = dict()
        self._send_request(GetReinjectionStatusMessage(x, y, p),
                           callback=self.handle_reinjection_status_response)
        self._finish()
        self.check_for_error()
        return self._reinjection_status[(x, y)]

    def get_reinjection_status_for_core_subsets(
            self, core_subsets):
        self._reinjection_status = dict()
        for core_subset in core_subsets.core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(GetReinjectionStatusMessage(
                    core_subset.x, core_subset.y, processor_id),
                    callback=self.handle_reinjection_status_response)
        self._finish()
        self.check_for_error()
        return self._reinjection_status
