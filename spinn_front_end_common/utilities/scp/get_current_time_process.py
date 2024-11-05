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
from spinnman.messages.scp.abstract_messages import (
    AbstractSCPRequest, AbstractSCPResponse)
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.impl import CheckOKResponse
from spinnman.processes import AbstractMultiConnectionProcess
from spinnman.model.enums import (
    SDP_PORTS, SDP_RUNNING_MESSAGE_CODES)
from spinnman.messages.scp.enums import SCPResult
from spinnman.exceptions import SpinnmanUnexpectedResponseCodeException


class _GetCurrentTimeRequest(AbstractSCPRequest[CheckOKResponse]):
    def __init__(self, x: int, y: int, p: int):
        """
        :param int x:
        :param int y:
        :param int p:
        """
        # pylint: disable=too-many-arguments
        sdp_flags = SDPFlag.REPLY_EXPECTED

        super().__init__(
            SDPHeader(
                flags=sdp_flags,
                destination_port=SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value,
                destination_cpu=p, destination_chip_x=x, destination_chip_y=y),
            SCPRequestHeader(
                command=SDP_RUNNING_MESSAGE_CODES.SDP_GET_CURRENT_TIME_CODE))

    @overrides(AbstractSCPRequest.get_scp_response)
    def get_scp_response(self) -> CheckOKResponse:
        return _GetCurrentTimeResponse()


class _GetCurrentTimeResponse(AbstractSCPResponse):

    __slots__ = (
        "__current_time",
    )

    def __init__(self):
        super().__init__()
        self.__current_time = None

    @overrides(AbstractSCPResponse.read_data_bytestring)
    def read_data_bytestring(self, data: bytes, offset: int):
        result = self.scp_response_header.result
        # We can accept a no-reply response here; that could just mean
        # that the count wasn't complete (but might be enough anyway)
        if result != SCPResult.RC_OK and result != SCPResult.RC_P2P_NOREPLY:
            raise SpinnmanUnexpectedResponseCodeException(
                "CountState", "CMD_COUNT", result.name)
        self.__current_time = struct.unpack_from("<I", data, offset)[0]

    @property
    def current_time(self) -> int:
        """ Get the current time from the response
        """
        return self.__current_time


class GetCurrentTimeProcess(AbstractMultiConnectionProcess[CheckOKResponse]):
    """
    How to update the target running time of a set of cores.

    .. note::
        The cores must be using the simulation interface.
    """
    __slots__ = (
        "__latest_time",
    )

    def __init__(self, connection_selector):
        super().__init__(connection_selector)
        self.__latest_time = None

    def __receive_response(
            self, progress: ProgressBar, response: _GetCurrentTimeResponse):
        progress.update()
        current_time = response.current_time
        header = response.sdp_header
        print(f"Current time from {header.destination_chip_x}, "
              f"{header.destination_chip_y}, {header.destination_cpu}: "
              f"{current_time}")
        if self.__latest_time is None or current_time > self.__latest_time:
            self.__latest_time = current_time

    def get_latest_runtime(
            self, n_cores: int, core_subsets: CoreSubsets) -> int:
        """
        :param ~spinn_machine.CoreSubsets core_subsets:
        :param int n_cores: Number of cores being updated
        """
        self.__latest_time = None
        with ProgressBar(n_cores, "Getting current time") as progress, \
                self._collect_responses():
            for core_subset in core_subsets:
                for processor_id in core_subset.processor_ids:
                    self._send_request(
                        _GetCurrentTimeRequest(
                            core_subset.x, core_subset.y, processor_id),
                        callback=partial(self.__receive_response, progress))
        self._finish()
        self.check_for_error()
        return self.__latest_time
