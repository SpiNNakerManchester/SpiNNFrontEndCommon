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
import logging
from typing import Optional
from spinn_utilities.overrides import overrides
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from spinn_machine import CoreSubsets
from spinnman.messages.sdp import SDPHeader, SDPFlag
from spinnman.messages.scp.abstract_messages import (
    AbstractSCPRequest, AbstractSCPResponse)
from spinnman.messages.scp import SCPRequestHeader
from spinnman.processes import (
    AbstractMultiConnectionProcess, MostDirectConnectionSelector)
from spinnman.model.enums import (
    SDP_PORTS, SDP_RUNNING_MESSAGE_CODES)
from spinnman.messages.scp.enums import SCPResult
from spinnman.exceptions import SpinnmanUnexpectedResponseCodeException

logger = FormatAdapter(logging.getLogger(__name__))


class _GetCurrentTimeResponse(AbstractSCPResponse):

    __slots__ = (
        "__current_time",
    )

    def __init__(self) -> None:
        super().__init__()
        self.__current_time: Optional[int] = None

    @overrides(AbstractSCPResponse.read_data_bytestring)
    def read_data_bytestring(self, data: bytes, offset: int) -> None:
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
        assert self.__current_time is not None
        return self.__current_time


class _GetCurrentTimeRequest(AbstractSCPRequest[_GetCurrentTimeResponse]):
    def __init__(self, x: int, y: int, p: int):
        """
        :param x:
        :param y:
        :param p:
        """
        sdp_flags = SDPFlag.REPLY_EXPECTED

        super().__init__(
            SDPHeader(
                flags=sdp_flags,
                destination_port=SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value,
                destination_cpu=p, destination_chip_x=x, destination_chip_y=y),
            SCPRequestHeader(
                command=SDP_RUNNING_MESSAGE_CODES.SDP_GET_CURRENT_TIME_CODE))

    @overrides(AbstractSCPRequest.get_scp_response)
    def get_scp_response(self) -> _GetCurrentTimeResponse:
        return _GetCurrentTimeResponse()


class GetCurrentTimeProcess(
        AbstractMultiConnectionProcess[_GetCurrentTimeResponse]):
    """
    How to update the target running time of a set of cores.

    .. note::
        The cores must be using the simulation interface.
    """
    __slots__ = (
        "__latest_time",
        "__earliest_time"
    )

    def __init__(self, connection_selector: MostDirectConnectionSelector):
        """
         :param connection_selector:
            Connection to send the request over.
        """
        super().__init__(connection_selector)
        self.__latest_time: Optional[int] = None
        self.__earliest_time: Optional[int] = None

    def __receive_response(self, progress: ProgressBar,
                           response: _GetCurrentTimeResponse) -> None:
        progress.update()
        current_time = response.current_time
        if self.__latest_time is None or current_time > self.__latest_time:
            self.__latest_time = current_time
        if self.__earliest_time is None or current_time < self.__earliest_time:
            self.__earliest_time = current_time

    def get_latest_runtime(
            self, n_cores: int, core_subsets: CoreSubsets) -> Optional[int]:
        """
        Reads the runtime off all cores in the subset

        Logger warns if not all cores reported the same runtime

        :param core_subsets:
        :param n_cores: Number of cores being updated
        :returns: The latest found
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

        if self.__earliest_time != self.__latest_time:
            logger.warning(
                "The cores did not all stop on the same time-step; on the "
                "next run, the simulation will start at the latest time of "
                f"{self.__latest_time}.  For information, the earliest time "
                f"was {self.__earliest_time}.")

        return self.__latest_time
