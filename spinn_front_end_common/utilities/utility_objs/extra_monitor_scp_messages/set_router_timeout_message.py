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

from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.sdp import SDPFlag, SDPHeader
from spinnman.messages.scp.impl.check_ok_response import CheckOKResponse
from spinn_front_end_common.utilities.constants import SDP_PORTS
from .reinjector_scp_commands import ReinjectorSCPCommands


class SetRouterTimeoutMessage(AbstractSCPRequest):
    """ An SCP Request to the extra monitor core to set the router timeout\
    for dropped packet reinjection
    """

    __slots__ = []

    def __init__(self, x, y, p, timeout_mantissa, timeout_exponent):
        """
        :param x: The x-coordinate of a chip, between 0 and 255
        :type x: int
        :param y: The y-coordinate of a chip, between 0 and 255
        :type y: int
        :param p: \
            The processor running the extra monitor vertex, between 0 and 17
        :type p: int
        :param timeout_mantissa: \
            The mantissa of the timeout value, between 0 and 15
        :type timeout_mantissa: int
        :param timeout_exponent: \
            The exponent of the timeout value, between 0 and 15
        :type timeout_exponent: int
        """
        # pylint: disable=too-many-arguments
        super(SetRouterTimeoutMessage, self).__init__(
            SDPHeader(
                flags=SDPFlag.REPLY_EXPECTED,
                destination_port=(
                    SDP_PORTS.EXTRA_MONITOR_CORE_REINJECTION.value),
                destination_cpu=p, destination_chip_x=x,
                destination_chip_y=y),
            SCPRequestHeader(command=ReinjectorSCPCommands.SET_ROUTER_TIMEOUT),
            argument_1=(timeout_mantissa & 0xF) |
                       ((timeout_exponent & 0xF) << 4))

    def get_scp_response(self):
        return CheckOKResponse(
            "Set router timeout", ReinjectorSCPCommands.SET_ROUTER_TIMEOUT)
