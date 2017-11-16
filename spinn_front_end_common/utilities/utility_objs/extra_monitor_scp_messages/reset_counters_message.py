from spinn_front_end_common.utilities import constants
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.sdp import SDPFlag, SDPHeader
from spinnman.messages.scp.impl.check_ok_response import CheckOKResponse


class ResetCountersMessage(AbstractSCPRequest):
    """ An SCP Request to reset the statistics counters of the dropped packet\
        reinjection
    """

    __slots__ = (
        # command code
        "_command_code"
    )

    def __init__(self, x, y, p, command_code):
        """
        :param x: The x-coordinate of a chip, between 0 and 255
        :type x: int
        :param y: The y-coordinate of a chip, between 0 and 255
        :type y: int
        :param p: The processor running the extra monitor vertex, between\
                0 and 17
        :type p: int
        :param command_code: the command code used by the extra monitor \
        vertex for resetting reinjection counters.
        """

        self._command_code = command_code
        AbstractSCPRequest.__init__(
            self,
            SDPHeader(
                flags=SDPFlag.REPLY_NOT_EXPECTED,
                destination_port=(
                    constants.SDP_PORTS.EXTRA_MONITOR_CORE_RE_INJECTION.value),
                destination_cpu=p, destination_chip_x=x,
                destination_chip_y=y),
            SCPRequestHeader(command=self._command_code))

    def get_scp_response(self):
        return CheckOKResponse(
            "Reset dropped packet reinjection counters", self._command_code)
