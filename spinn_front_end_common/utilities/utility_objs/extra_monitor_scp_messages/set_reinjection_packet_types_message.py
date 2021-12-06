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

import struct
from spinn_utilities.overrides import overrides
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.sdp import SDPFlag, SDPHeader
from spinnman.messages.scp.impl.check_ok_response import CheckOKResponse
from spinn_front_end_common.utilities.constants import SDP_PORTS
from .reinjector_scp_commands import ReinjectorSCPCommands


class SetReinjectionPacketTypesMessage(AbstractSCPRequest):
    """ An SCP Request to set the dropped packet reinjected packet types.
    """

    __slots__ = []

    def __init__(self, x, y, p, multicast, point_to_point, fixed_route,
                 nearest_neighbour):
        """
        :param int x: The x-coordinate of a chip, between 0 and 255
        :param int y: The y-coordinate of a chip, between 0 and 255
        :param int p:
            The processor running the extra monitor vertex, between 0 and 17
        :param bool point_to_point: If point to point should be set
        :param bool multicast: If multicast should be set
        :param bool nearest_neighbour: If nearest neighbour should be set
        :param bool fixed_route: If fixed route should be set
        """
        # pylint: disable=too-many-arguments
        super().__init__(
            SDPHeader(
                flags=SDPFlag.REPLY_EXPECTED,
                destination_port=(
                    SDP_PORTS.EXTRA_MONITOR_CORE_REINJECTION.value),
                destination_cpu=p, destination_chip_x=x,
                destination_chip_y=y),
            SCPRequestHeader(command=ReinjectorSCPCommands.SET_PACKET_TYPES),
            argument_1=int(bool(multicast)),
            argument_2=int(bool(point_to_point)),
            argument_3=int(bool(fixed_route)),
            data=bytearray(struct.pack("<B", nearest_neighbour)))

    @overrides(AbstractSCPRequest.get_scp_response)
    def get_scp_response(self):
        return CheckOKResponse(
            "Set reinjected packet types",
            ReinjectorSCPCommands.SET_PACKET_TYPES)
