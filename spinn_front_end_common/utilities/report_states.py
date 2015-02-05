from pacman.utilities.report_states import ReportState as PacmanReportState


class ReportState(object):

    def __init__(self, execute_parittioner_report, execute_placer_report,
                 execute_router_report, execute_router_dat_based_report,
                 execute_routing_info_report, execute_data_spec_report,
                 execute_write_reload_steps, generate_transciever_report,
                 generate_time_recordings_for_performance_measurements):

        self._partitioner_report = execute_parittioner_report
        self._placer_report = execute_placer_report
        self._router_report = execute_router_report
        self._router_dat_based_report = execute_router_dat_based_report
        self._routing_info_report = execute_routing_info_report
        self._data_spec_report = execute_data_spec_report
        self._write_reload_steps = execute_write_reload_steps
        self._transciever_report = generate_transciever_report
        self._generate_time_recordings_for_performance_measurements = \
            generate_time_recordings_for_performance_measurements

    @property
    def partitioner_report(self):
        return self._partitioner_report

    @property
    def placer_report(self):
        return self._placer_report

    @property
    def router_report(self):
        return self._router_report

    @property
    def router_dat_based_report(self):
        return self._router_dat_based_report

    @property
    def routing_info_report(self):
        return self._routing_info_report

    @property
    def data_spec_report(self):
        return self._data_spec_report

    @property
    def write_reload_steps(self):
        return self._write_reload_steps

    @property
    def transciever_report(self):
        return self._transciever_report

    @property
    def generate_time_recordings_for_performance_measurements(self):
        return self._generate_time_recordings_for_performance_measurements

    def generate_pacman_report_states(self):
        return PacmanReportState(
            self._partitioner_report, self._placer_report, self._router_report,
            self._router_dat_based_report, self._routing_info_report)
