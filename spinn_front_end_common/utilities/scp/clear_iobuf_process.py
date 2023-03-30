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

from spinn_utilities.progress_bar import ProgressBar
from spinnman.messages.sdp import SDPHeader, SDPFlag
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.impl import CheckOKResponse
from spinnman.processes import AbstractMultiConnectionProcess
from spinn_front_end_common.utilities.constants import (
    SDP_PORTS, SDP_RUNNING_MESSAGE_CODES)


class _ClearIOBUFRequest(AbstractSCPRequest):
    def __init__(self, x, y, p):

        super().__init__(
            SDPHeader(
                flags=SDPFlag.REPLY_EXPECTED,
                destination_cpu=p, destination_chip_x=x, destination_chip_y=y,
                destination_port=SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value),
            SCPRequestHeader(
                command=SDP_RUNNING_MESSAGE_CODES.SDP_CLEAR_IOBUF_CODE),
            argument_3=int(True))

    def get_scp_response(self):
        return CheckOKResponse(
            "clear iobuf",
            SDP_RUNNING_MESSAGE_CODES.SDP_CLEAR_IOBUF_CODE.value)


class ClearIOBUFProcess(AbstractMultiConnectionProcess):
    """
    How to clear the IOBUF buffers of a set of cores.

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

    def clear_iobuf(self, core_subsets, n_cores=None):
        """
        :param ~spinn_machine.CoreSubsets core_subsets:
        :param int n_cores: Defaults to the number of cores in `core_subsets`.
        """
        if n_cores is None:
            n_cores = len(core_subsets)
        self._progress = ProgressBar(
            n_cores, "clearing IOBUF from the machine")
        for core_subset in core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(
                    _ClearIOBUFRequest(
                        core_subset.x, core_subset.y, processor_id),
                    callback=self.__receive_response)
        self._finish()
        self._progress.end()
        self._progress = None
        self.check_for_error()
