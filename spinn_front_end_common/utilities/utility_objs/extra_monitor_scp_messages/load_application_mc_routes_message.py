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

from spinn_front_end_common.utilities.constants import SDP_PORTS
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.sdp import SDPFlag, SDPHeader
from spinnman.messages.scp.impl.check_ok_response import CheckOKResponse
from .speedup_in_scp_commands import SpeedupInSCPCommands


class LoadApplicationMCRoutesMessage(AbstractSCPRequest):
    """ An SCP Request to write the application multicast routes into the\
    router.
    """

    __slots__ = (
    )

    def __init__(self, x, y, p):
        """
        :param x: The x-coordinate of a chip, between 0 and 255
        :type x: int
        :param y: The y-coordinate of a chip, between 0 and 255
        :type y: int
        :param p: The processor running the extra monitor vertex, between\
            0 and 17
        :type p: int
        """
        super(LoadApplicationMCRoutesMessage, self).__init__(
            SDPHeader(
                flags=SDPFlag.REPLY_EXPECTED,
                destination_port=(
                    SDP_PORTS.EXTRA_MONITOR_CORE_DATA_IN_SPEED_UP.value),
                destination_cpu=p, destination_chip_x=x,
                destination_chip_y=y),
            SCPRequestHeader(
                command=SpeedupInSCPCommands.LOAD_APPLICATION_MC_ROUTES))

    def get_scp_response(self):
        return CheckOKResponse(
            "load application multicast routes",
            SpeedupInSCPCommands.LOAD_APPLICATION_MC_ROUTES)
