from spinn_machine.utilities.progress_bar import ProgressBar

from spinn_front_end_common.utilities.scp.scp_clear_iobuf_request import \
    SCPClearIOBUFRequest
from spinn_front_end_common.utilities import constants
from spinnman.processes.abstract_multi_connection_process \
    import AbstractMultiConnectionProcess


class ClearIOBUFProcess(AbstractMultiConnectionProcess):

    def __init__(self, connection_selector):
        AbstractMultiConnectionProcess.__init__(self, connection_selector)
        self._progress_bar = None

    def receive_response(self, response):
        if self._progress_bar is not None:
            self._progress_bar.update()

    def clear_iobuf(self, core_subsets, n_cores):
        self._progress_bar = ProgressBar(
            n_cores, "clearing IOBUF from the machine")
        for core_subset in core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(
                    SCPClearIOBUFRequest(
                        core_subset.x, core_subset.y, processor_id,
                        constants.SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value),
                    callback=self.receive_response)
        self._finish()
        self._progress_bar.end()
        self.check_for_error()
