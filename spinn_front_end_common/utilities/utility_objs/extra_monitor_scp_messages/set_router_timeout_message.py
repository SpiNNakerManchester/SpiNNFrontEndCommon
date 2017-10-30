from spinn_front_end_common.utility_models.\
    extra_monitor_support_machine_vertex import \
    ExtraMonitorSupportMachineVertex
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.sdp import SDPFlag, SDPHeader
from spinnman.messages.scp.impl.check_ok_response import CheckOKResponse


class SetRouterTimeoutMessage(AbstractSCPRequest):
    """ An SCP Request to the extra monitor core to set the router timeout 
    for dropped packet reinjection
    """

    def __init__(self, x, y, p, timeout_mantissa, timeout_exponent):
        """
        :param x: The x-coordinate of a chip, between 0 and 255
        :type x: int
        :param y: The y-coordinate of a chip, between 0 and 255
        :type y: int
        :param p: The processor running the dropped packet reinjector, between\
                0 and 17
        :type p: int
        :param timeout_mantissa: The mantissa of the timeout value, \
                between 0 and 15
        :type timeout_mantissa: int
        :param timeout_exponent: The exponent of the timeout value, \
                between 0 and 15
        """
        AbstractSCPRequest.__init__(
            self,
            SDPHeader(
                flags=SDPFlag.REPLY_EXPECTED, destination_port=0,
                destination_cpu=p, destination_chip_x=x,
                destination_chip_y=y),
            SCPRequestHeader(command=ExtraMonitorSupportMachineVertex.
            EXTRA_MONITOR_COMMANDS.SET_ROUTER_TIMEOUT.value()),
            argument_1=(timeout_mantissa & 0xF) |
                       ((timeout_exponent & 0xF) << 4))

    def get_scp_response(self):
        return CheckOKResponse(
            "Set router timeout", ExtraMonitorSupportMachineVertex.
            EXTRA_MONITOR_COMMANDS.SET_ROUTER_TIMEOUT.value())
