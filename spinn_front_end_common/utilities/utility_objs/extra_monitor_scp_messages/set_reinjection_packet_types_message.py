from spinn_front_end_common.utilities import constants
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.sdp import SDPFlag, SDPHeader
from spinnman.messages.scp.impl.check_ok_response import CheckOKResponse
import struct


class SetReinjectionPacketTypesMessage(AbstractSCPRequest):
    """ An SCP Request to set the dropped packet reinjected packet types
    """

    def __init__(self, x, y, p, multicast, point_to_point, fixed_route,
                 nearest_neighbour, command_code):
        """
        :param x: The x-coordinate of a chip, between 0 and 255
        :type x: int
        :param y: The y-coordinate of a chip, between 0 and 255
        :type y: int
        :param p: \
            The processor running the extra monitor vertex, between 0 and 17
        :type p: int
        :param point_to_point: If point to point should be set
        :type point_to_point: bool
        :param multicast: If multicast should be set
        :type multicast: bool
        :param nearest_neighbour: If nearest neighbour should be set
        :type nearest_neighbour: bool
        :param fixed_route: If fixed route should be set
        :type fixed_route: bool
        :param command_code: \
            the code used by the extra monitor vertex for set packet types
        :type command_code: \
            :py:class:`spinnman.messages.scp.scp_command.SCPCommand`
        """
        # pylint: disable=too-many-arguments
        self._command_code = command_code
        super(SetReinjectionPacketTypesMessage, self).__init__(
            SDPHeader(
                flags=SDPFlag.REPLY_EXPECTED,
                destination_port=(
                    constants.SDP_PORTS.EXTRA_MONITOR_CORE_REINJECTION.value),
                destination_cpu=p, destination_chip_x=x,
                destination_chip_y=y),
            SCPRequestHeader(command=self._command_code),
            argument_1=int(bool(multicast)),
            argument_2=int(bool(point_to_point)),
            argument_3=int(bool(fixed_route)),
            data=bytearray(struct.pack("<B", nearest_neighbour)))

    def get_scp_response(self):
        return CheckOKResponse(
            "Set reinjected packet types", self._command_code)
