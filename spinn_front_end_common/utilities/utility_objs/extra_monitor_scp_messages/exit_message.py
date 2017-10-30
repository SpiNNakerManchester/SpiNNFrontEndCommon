from spinn_front_end_common.utility_models.\
    extra_monitor_support_machine_vertex import \
    ExtraMonitorSupportMachineVertex
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.sdp import SDPFlag, SDPHeader
from spinnman.messages.scp.impl.check_ok_response import CheckOKResponse


class ExitMessage(AbstractSCPRequest):
    """ An SCP Request for the extra monitor functionality to exit
    """

    def __init__(self, x, y, p):
        """
        :param x: The x-coordinate of a chip, between 0 and 255
        :type x: int
        :param y: The y-coordinate of a chip, between 0 and 255
        :type y: int
        :param p: The processor running the dropped packet reinjector, between\
                0 and 17
        :type p: int
        """
        AbstractSCPRequest.__init__(
            self,
            SDPHeader(
                flags=SDPFlag.REPLY_EXPECTED, destination_port=0,
                destination_cpu=p, destination_chip_x=x,
                destination_chip_y=y),
            SCPRequestHeader(
                command=
                ExtraMonitorSupportMachineVertex.EXTRA_MONITOR_COMMANDS.EXIT.
                value()))

    def get_scp_response(self):
        return CheckOKResponse(
            "Exit dropped packet reinjection",
            ExtraMonitorSupportMachineVertex.EXTRA_MONITOR_COMMANDS.EXIT.
            value())
