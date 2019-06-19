from spinn_front_end_common.utilities.utility_objs.\
    extra_monitor_scp_messages import (
        LoadApplicationMCRoutesMessage)
from spinnman.processes.abstract_multi_connection_process import (
    AbstractMultiConnectionProcess)


class LoadApplicationMCRoutesProcess(AbstractMultiConnectionProcess):
    def load_application_mc_routes(self, core_subsets):
        """
        :param core_subsets: sets of cores to send command to
        :rtype: None
        """
        for core_subset in core_subsets.core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(LoadApplicationMCRoutesMessage(
                    core_subset.x, core_subset.y, processor_id))
        self._finish()
        self.check_for_error()
