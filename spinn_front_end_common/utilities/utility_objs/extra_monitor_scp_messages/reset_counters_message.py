from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.sdp import SDPFlag, SDPHeader
from spinnman.messages.scp.impl.check_ok_response import CheckOKResponse
from spinn_front_end_common.utilities.constants import SDP_PORTS
from .reinjector_scp_commands import ReinjectorSCPCommands


class ResetCountersMessage(AbstractSCPRequest):
    """ An SCP Request to reset the statistics counters of the dropped packet\
        reinjection
    """

    __slots__ = []

    def __init__(self, x, y, p):
        """
        :param x: The x-coordinate of a chip, between 0 and 255
        :type x: int
        :param y: The y-coordinate of a chip, between 0 and 255
        :type y: int
        :param p: \
            The processor running the extra monitor vertex, between 0 and 17
        :type p: int
        """

        super(ResetCountersMessage, self).__init__(
            SDPHeader(
                flags=SDPFlag.REPLY_NOT_EXPECTED,
                destination_port=(
                    SDP_PORTS.EXTRA_MONITOR_CORE_REINJECTION.value),
                destination_cpu=p, destination_chip_x=x,
                destination_chip_y=y),
            SCPRequestHeader(command=ReinjectorSCPCommands.RESET_COUNTERS))

    def get_scp_response(self):
        return CheckOKResponse(
            "Reset dropped packet reinjection counters",
            ReinjectorSCPCommands.RESET_COUNTERS)
