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

from spinn_utilities.overrides import overrides
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.sdp import SDPFlag, SDPHeader
from spinnman.messages.scp.impl.check_ok_response import CheckOKResponse
from spinnman.model.enums import SDP_PORTS
from .reinjector_scp_commands import ReinjectorSCPCommands


class SetRouterTimeoutMessage(AbstractSCPRequest[CheckOKResponse]):
    """
    An SCP Request to the extra monitor core to set the router timeout
    for dropped packet reinjection.
    """

    __slots__ = ()

    def __init__(self, x: int, y: int, p: int, *,
                 timeout_mantissa: int, timeout_exponent: int, wait: int):
        """
        :param x: The x-coordinate of a chip
        :param y: The y-coordinate of a chip
        :param p: The processor running the extra monitor vertex
        :param timeout_mantissa:
            The mantissa of the timeout value, between 0 and 15
        :param timeout_exponent:
            The exponent of the timeout value, between 0 and 15
        :param wait:
            Which wait to set. Should be 1 or 2.
        """
        cmd = ReinjectorSCPCommands.SET_ROUTER_WAIT1_TIMEOUT if wait == 1 \
            else ReinjectorSCPCommands.SET_ROUTER_WAIT2_TIMEOUT
        super().__init__(
            SDPHeader(
                flags=SDPFlag.REPLY_EXPECTED,
                destination_port=(
                    SDP_PORTS.EXTRA_MONITOR_CORE_REINJECTION.value),
                destination_cpu=p, destination_chip_x=x,
                destination_chip_y=y),
            SCPRequestHeader(command=cmd),
            argument_1=(timeout_mantissa & 0xF) |
                       ((timeout_exponent & 0xF) << 4))

    @overrides(AbstractSCPRequest.get_scp_response)
    def get_scp_response(self) -> CheckOKResponse:
        return CheckOKResponse("Set router timeout",
                               self.scp_request_header.command)
