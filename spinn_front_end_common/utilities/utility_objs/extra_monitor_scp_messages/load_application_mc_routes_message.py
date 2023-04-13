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
from spinn_front_end_common.utilities.constants import SDP_PORTS
from .speedup_in_scp_commands import SpeedupInSCPCommands


class LoadApplicationMCRoutesMessage(AbstractSCPRequest):
    """
    An SCP Request to write the application multicast routes into the router.
    """

    __slots__ = (
    )

    def __init__(self, x, y, p):
        """
        :param int x: The x-coordinate of a chip, between 0 and 255
        :param int y: The y-coordinate of a chip, between 0 and 255
        :param int p:
            The processor running the extra monitor vertex, between 0 and 17
        """
        super().__init__(
            SDPHeader(
                flags=SDPFlag.REPLY_EXPECTED,
                destination_port=(
                    SDP_PORTS.EXTRA_MONITOR_CORE_DATA_IN_SPEED_UP.value),
                destination_cpu=p, destination_chip_x=x,
                destination_chip_y=y),
            SCPRequestHeader(
                command=SpeedupInSCPCommands.LOAD_APPLICATION_MC_ROUTES))

    @overrides(AbstractSCPRequest.get_scp_response)
    def get_scp_response(self):
        return CheckOKResponse(
            "load application multicast routes",
            SpeedupInSCPCommands.LOAD_APPLICATION_MC_ROUTES)
