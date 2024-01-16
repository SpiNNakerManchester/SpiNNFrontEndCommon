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

from functools import partial
import struct
from spinn_utilities.overrides import overrides
from spinn_utilities.progress_bar import ProgressBar
from spinn_machine import CoreSubsets
from spinnman.messages.sdp import SDPHeader, SDPFlag
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.impl import CheckOKResponse
from spinnman.processes import AbstractMultiConnectionProcess
from spinnman.model.enums import (
    SDP_PORTS, SDP_RUNNING_MESSAGE_CODES)


class _UpdateRuntimeRequest(AbstractSCPRequest[CheckOKResponse]):
    def __init__(self, x: int, y: int, p: int, current_time: int,
                 run_time: int, infinite_run: bool, n_sync_steps: int):
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
            argument_1=run_time, argument_2=int(infinite_run),
            argument_3=current_time,
            data=struct.pack("<I", int(n_sync_steps)))

    @overrides(AbstractSCPRequest.get_scp_response)
    def get_scp_response(self) -> CheckOKResponse:
        return CheckOKResponse(
            "update runtime",
            SDP_RUNNING_MESSAGE_CODES.SDP_NEW_RUNTIME_ID_CODE.value)


class UpdateRuntimeProcess(AbstractMultiConnectionProcess[CheckOKResponse]):
    """
    How to update the target running time of a set of cores.

    .. note::
        The cores must be using the simulation interface.
    """
    __slots__ = ()

    def __receive_response(
            self, progress: ProgressBar, _response: CheckOKResponse):
        progress.update()

    def update_runtime(
            self, current_time: int, run_time: int, infinite_run: bool,
            core_subsets: CoreSubsets, n_cores: int, n_sync_steps: int):
        """
        :param int current_time:
        :param int run_time:
        :param bool infinite_run:
        :param ~spinn_machine.CoreSubsets core_subsets:
        :param int n_cores: Number of cores being updated
        :param int n_sync_steps:
        """
        with ProgressBar(n_cores, "Updating run time") as progress, \
                self._collect_responses():
            for core_subset in core_subsets:
                for processor_id in core_subset.processor_ids:
                    self._send_request(
                        _UpdateRuntimeRequest(
                            core_subset.x, core_subset.y, processor_id,
                            current_time, run_time, infinite_run,
                            n_sync_steps),
                        callback=partial(self.__receive_response, progress))
