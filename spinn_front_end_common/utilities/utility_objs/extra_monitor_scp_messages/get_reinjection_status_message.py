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

from typing import Optional
from spinn_utilities.overrides import overrides
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.abstract_messages import (
    AbstractSCPRequest, AbstractSCPResponse)
from spinnman.messages.scp.enums import SCPResult
from spinnman.messages.sdp import SDPFlag, SDPHeader
from spinnman.model.enums import SDP_PORTS
from spinnman.exceptions import SpinnmanUnexpectedResponseCodeException
from spinn_front_end_common.utilities.utility_objs import ReInjectionStatus
from .reinjector_scp_commands import ReinjectorSCPCommands


class GetReinjectionStatusMessage(
        AbstractSCPRequest['GetReinjectionStatusMessageResponse']):
    """
    An SCP Request to get the status of the dropped packet reinjection.
    """
    __slots__ = ()

    def __init__(self, x: int, y: int, p: int) -> None:
        """
        :param x: The x-coordinate of a chip
        :param y: The y-coordinate of a chip
        :param p: The processor running the extra monitor vertex
        """
        super().__init__(
            SDPHeader(
                flags=SDPFlag.REPLY_EXPECTED,
                destination_port=(
                    SDP_PORTS.EXTRA_MONITOR_CORE_REINJECTION.value),
                destination_cpu=p, destination_chip_x=x,
                destination_chip_y=y),
            SCPRequestHeader(command=ReinjectorSCPCommands.GET_STATUS))

    @overrides(AbstractSCPRequest.get_scp_response)
    def get_scp_response(self) -> 'GetReinjectionStatusMessageResponse':
        return GetReinjectionStatusMessageResponse(
            ReinjectorSCPCommands.GET_STATUS)


class GetReinjectionStatusMessageResponse(AbstractSCPResponse):
    """
    An SCP response to a request for the dropped packet reinjection status
    """
    __slots__ = ("_reinjection_status", "_command_code")

    def __init__(self, command_code: ReinjectorSCPCommands):
        super().__init__()
        self._reinjection_status: Optional[ReInjectionStatus] = None
        self._command_code = command_code

    @overrides(AbstractSCPResponse.read_data_bytestring)
    def read_data_bytestring(self, data: bytes, offset: int) -> None:
        result = self.scp_response_header.result
        if result != SCPResult.RC_OK:
            raise SpinnmanUnexpectedResponseCodeException(
                "Get packet reinjection status",
                str(self._command_code), result.name)
        self._reinjection_status = ReInjectionStatus(data, offset)

    @property
    def reinjection_functionality_status(self) -> ReInjectionStatus:
        """
        Gets the reinjection functionality status

        :raises AssertError: If not yet read
        """
        assert self._reinjection_status is not None, "response not yet read"
        return self._reinjection_status
