from spinnman.messages.sdp import SDPHeader, SDPFlag
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.impl import CheckOKResponse
from spinn_front_end_common.utilities.constants import (
    SDP_RUNNING_MESSAGE_CODES)


class SCPClearIOBUFRequest(AbstractSCPRequest):

    def __init__(
            self, x, y, p, destination_port, expect_response=True):
        # pylint: disable=too-many-arguments
        sdp_flags = SDPFlag.REPLY_NOT_EXPECTED
        if expect_response:
            sdp_flags = SDPFlag.REPLY_EXPECTED

        super(SCPClearIOBUFRequest, self).__init__(
            SDPHeader(
                flags=sdp_flags, destination_port=destination_port,
                destination_cpu=p, destination_chip_x=x, destination_chip_y=y),
            SCPRequestHeader(
                command=SDP_RUNNING_MESSAGE_CODES.SDP_CLEAR_IOBUF_CODE),
            argument_3=int(bool(expect_response)))

    def get_scp_response(self):
        return CheckOKResponse(
            "clear iobuf",
            SDP_RUNNING_MESSAGE_CODES.SDP_CLEAR_IOBUF_CODE.value)
