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
        :param p: The processor running the dropped packet reinjector, between\
                0 and 17
        :type p: int
        :param point_to_point: bool stating if point to point should be set
        :param multicast: bool stating if multicast should be set
        :param nearest_neighbour: bool stating if nearest neighbour should be \
        set
        :param fixed_route: bool stating if fixed route should be set
        :param command_code: the code used by the extra monitor vertex for \
        set packet types
        
        """

        self._command_code = command_code
        AbstractSCPRequest.__init__(
            self,
            SDPHeader(
                flags=SDPFlag.REPLY_EXPECTED,
                destination_port=
                constants.SDP_PORTS.EXTRA_MONITOR_CORE_RE_INJECTION.value,
                destination_cpu=p, destination_chip_x=x,
                destination_chip_y=y),
            SCPRequestHeader(command=self._command_code),
            argument_1=multicast, argument_2=point_to_point,
            argument_3=fixed_route, data=bytearray(
                struct.pack("<B", nearest_neighbour)))

    def get_scp_response(self):
        return CheckOKResponse(
            "Set reinjected packet types", self._command_code)
