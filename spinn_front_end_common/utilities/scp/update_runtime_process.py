# Copyright (c) 2016 The University of Manchester
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

import struct
from spinn_utilities.progress_bar import ProgressBar
from spinnman.messages.sdp import SDPHeader, SDPFlag
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.impl import CheckOKResponse
from spinnman.processes import AbstractMultiConnectionProcess
from spinn_front_end_common.utilities.constants import (
    SDP_PORTS, SDP_RUNNING_MESSAGE_CODES)
from spinn_utilities.overrides import overrides


class _UpdateRuntimeRequest(AbstractSCPRequest):
    def __init__(
            self, x, y, p, current_time, run_time, infinite_run, n_sync_steps):
        """
        :param int x:
        :param int y:
        :param int p:
        :param int current_time:
        :param int run_time:
        :param bool infinite_run:
        :param int n_sync_steps:
        """
        # pylint: disable=too-many-arguments
        sdp_flags = SDPFlag.REPLY_EXPECTED

        super().__init__(
            SDPHeader(
                flags=sdp_flags,
                destination_port=SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value,
                destination_cpu=p, destination_chip_x=x, destination_chip_y=y),
            SCPRequestHeader(
                command=SDP_RUNNING_MESSAGE_CODES.SDP_NEW_RUNTIME_ID_CODE),
            argument_1=run_time, argument_2=infinite_run,
            argument_3=current_time,
            data=struct.pack("<I", int(n_sync_steps)))

    @overrides(AbstractSCPRequest.get_scp_response)
    def get_scp_response(self):
        return CheckOKResponse(
            "update runtime",
            SDP_RUNNING_MESSAGE_CODES.SDP_NEW_RUNTIME_ID_CODE.value)


class UpdateRuntimeProcess(AbstractMultiConnectionProcess):
    """
    How to update the target running time of a set of cores.

    .. note::
        The cores must be using the simulation interface.
    """

    def __init__(self, connection_selector):
        """
        :param connection_selector:
        :type connection_selector:
            ~spinnman.processes.abstract_multi_connection_process_connection_selector.AbstractMultiConnectionProcessConnectionSelector
        """
        super().__init__(connection_selector)
        self._progress = None

    def __receive_response(self, _response):
        if self._progress is not None:
            self._progress.update()

    def update_runtime(self, current_time, run_time, infinite_run,
                       core_subsets, n_cores, n_sync_steps):
        """
        :param int current_time:
        :param int run_time:
        :param bool infinite_run:
        :param ~spinn_machine.CoreSubsets core_subsets:
        :param int n_cores: Number of cores being updated
        """
        self._progress = ProgressBar(n_cores, "Updating run time")
        for core_subset in core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(
                    _UpdateRuntimeRequest(
                        core_subset.x, core_subset.y, processor_id,
                        current_time, run_time, infinite_run, n_sync_steps),
                    callback=self.__receive_response)
        self._finish()
        self._progress.end()
        self._progress = None
        self.check_for_error()
