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

from spinn_machine import CoreSubsets
from spinnman.processes import AbstractMultiConnectionProcess
from spinnman.messages.scp.impl import CheckOKResponse
from spinn_front_end_common.utilities.utility_objs.\
    extra_monitor_scp_messages import (
        LoadApplicationMCRoutesMessage, LoadSystemMCRoutesMessage)


class LoadMCRoutesProcess(AbstractMultiConnectionProcess[CheckOKResponse]):
    """
    How to send messages to load the saved multicast routing tables.
    """
    __slots__ = ()

    def load_application_mc_routes(self, core_subsets: CoreSubsets) -> None:
        """
        Load the saved application multicast routes.

        :param core_subsets: sets of cores to send command to
        """
        with self._collect_responses():
            for core_subset in core_subsets.core_subsets:
                for processor_id in core_subset.processor_ids:
                    self._send_request(LoadApplicationMCRoutesMessage(
                        core_subset.x, core_subset.y, processor_id))

    def load_system_mc_routes(self, core_subsets: CoreSubsets) -> None:
        """
        Load the saved system multicast routes.

        :param core_subsets: sets of cores to send command to
        """
        with self._collect_responses():
            for core_subset in core_subsets.core_subsets:
                for processor_id in core_subset.processor_ids:
                    self._send_request(LoadSystemMCRoutesMessage(
                        core_subset.x, core_subset.y, processor_id))
