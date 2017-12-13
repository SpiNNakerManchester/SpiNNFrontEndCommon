from spinn_front_end_common.utilities import constants
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.sdp import SDPFlag, SDPHeader
from spinnman.messages.scp.impl.check_ok_response import CheckOKResponse


class SetRouterTimeoutMessage(AbstractSCPRequest):
    """ An SCP Request to the extra monitor core to set the router timeout\
    for dropped packet reinjection
    """

    __slots__ = [
        # command code
        "_command_code"
    ]

    def __init__(self, x, y, p, timeout_mantissa, timeout_exponent,
                 command_code):
        """
        :param x: The x-coordinate of a chip, between 0 and 255
        :type x: int
        :param y: The y-coordinate of a chip, between 0 and 255
        :type y: int
        :param p: The processor running the extra monitor vertex, between\
                0 and 17
        :type p: int
        :param timeout_mantissa: The mantissa of the timeout value, \
                between 0 and 15
        :type timeout_mantissa: int
        :param timeout_exponent: The exponent of the timeout value, \
                between 0 and 15
        :param command_code: the code used by the extra monitor vertex for \
        setting the emergency timeout value
        """

        self._command_code = command_code
        AbstractSCPRequest.__init__(
            self,
            SDPHeader(
                flags=SDPFlag.REPLY_EXPECTED,
                destination_port=(
                    constants.SDP_PORTS.EXTRA_MONITOR_CORE_REINJECTION.value),
                destination_cpu=p, destination_chip_x=x,
                destination_chip_y=y),
            SCPRequestHeader(command=self._command_code),
            argument_1=(timeout_mantissa & 0xF) |
                       ((timeout_exponent & 0xF) << 4))

    def get_scp_response(self):
        return CheckOKResponse("Set router timeout", self._command_code)
