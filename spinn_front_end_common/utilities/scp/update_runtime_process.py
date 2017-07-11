from spinn_utilities.progress_bar import ProgressBar
from .scp_update_runtime_request import SCPUpdateRuntimeRequest
from spinn_front_end_common.utilities.constants import SDP_PORTS
from spinnman.processes import AbstractMultiConnectionProcess


class UpdateRuntimeProcess(AbstractMultiConnectionProcess):
    def __init__(self, connection_selector):
        AbstractMultiConnectionProcess.__init__(self, connection_selector)
        self._progress = None

    def receive_response(self, response):  # @UnusedVariable
        if self._progress is not None:
            self._progress.update()

    def update_runtime(self, run_time, infinite_run, core_subsets, n_cores):
        self._progress = ProgressBar(n_cores, "Updating run time")
        for core_subset in core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(
                    SCPUpdateRuntimeRequest(
                        core_subset.x, core_subset.y, processor_id,
                        run_time, infinite_run,
                        SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value),
                    callback=self.receive_response)
        self._finish()
        self._progress.end()
        self.check_for_error()
