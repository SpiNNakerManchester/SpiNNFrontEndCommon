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

from spinn_utilities.overrides import overrides
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.sdp import SDPFlag, SDPHeader
from spinnman.messages.scp.impl.check_ok_response import CheckOKResponse
from spinn_front_end_common.utilities.constants import SDP_PORTS
from .reinjector_scp_commands import ReinjectorSCPCommands


class SetRouterTimeoutMessage(AbstractSCPRequest):
    """ An SCP Request to the extra monitor core to set the router timeout\
        for dropped packet reinjection.
    """

    __slots__ = []

    def __init__(self, x, y, p, timeout_mantissa, timeout_exponent, wait=1):
        """
        :param int x: The x-coordinate of a chip, between 0 and 255
        :param int y: The y-coordinate of a chip, between 0 and 255
        :param int p:
            The processor running the extra monitor vertex, between 0 and 17
        :param int timeout_mantissa:
            The mantissa of the timeout value, between 0 and 15
        :param int timeout_exponent:
            The exponent of the timeout value, between 0 and 15
        :param int wait:
            Which wait to set. Should be 1 or 2.
        """
        # pylint: disable=too-many-arguments
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
    def get_scp_response(self):
        return CheckOKResponse("Set router timeout",
                               self.scp_request_header.command)
