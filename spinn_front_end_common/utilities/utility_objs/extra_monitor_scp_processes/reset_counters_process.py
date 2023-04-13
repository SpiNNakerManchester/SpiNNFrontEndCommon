# Copyright (c) 2017 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from spinnman.processes import AbstractMultiConnectionProcess
from spinn_front_end_common.utilities.utility_objs.extra_monitor_scp_messages\
    import (
        ResetCountersMessage)


class ResetCountersProcess(AbstractMultiConnectionProcess):
    """
    How to send messages to clear the reinjection state counters.
    """

    def reset_counters(self, core_subsets):
        """
        :param ~spinn_machine.CoreSubsets core_subsets:
        """
        for core_subset in core_subsets.core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(ResetCountersMessage(
                    core_subset.x, core_subset.y, processor_id))
        self._finish()
        self.check_for_error()
