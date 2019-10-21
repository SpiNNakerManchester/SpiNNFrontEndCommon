# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from spinn_utilities.progress_bar import ProgressBar
from spinnman.processes import AbstractMultiConnectionProcess
from .scp_update_runtime_request import SCPUpdateRuntimeRequest
from spinn_front_end_common.utilities.constants import SDP_PORTS


class UpdateRuntimeProcess(AbstractMultiConnectionProcess):
    def __init__(self, connection_selector):
        super(UpdateRuntimeProcess, self).__init__(connection_selector)
        self._progress = None

    def receive_response(self, _response):
        if self._progress is not None:
            self._progress.update()

    def update_runtime(self, current_time, run_time, infinite_run,
                       core_subsets, n_cores):
        self._progress = ProgressBar(n_cores, "Updating run time")
        for core_subset in core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(
                    SCPUpdateRuntimeRequest(
                        core_subset.x, core_subset.y, processor_id,
                        current_time, run_time, infinite_run,
                        SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value),
                    callback=self.receive_response)
        self._finish()
        self._progress.end()
        self.check_for_error()
