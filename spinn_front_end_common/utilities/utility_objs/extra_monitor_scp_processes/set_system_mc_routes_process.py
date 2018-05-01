from spinn_front_end_common.utilities.utility_objs.\
    extra_monitor_scp_messages.set_system_mc_routes_message import \
    SetSystemMCRoutesMessage
from spinnman.processes.abstract_multi_connection_process \
    import AbstractMultiConnectionProcess


class SetSystemMCRoutesProcess(AbstractMultiConnectionProcess):
    def set_system_mc_routes(self, core_subsets, command_code):
        """
        :param core_subsets: sets of cores to send command to
        :param command_code: the command code used by extra monitor cores
        for setting the system mc routes
        :rtype: None
        """
        for core_subset in core_subsets.core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(SetSystemMCRoutesMessage(
                    core_subset.x, core_subset.y, processor_id,
                    command_code))
        self._finish()
        self.check_for_error()
