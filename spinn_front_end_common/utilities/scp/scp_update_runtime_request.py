from spinnman.messages.sdp import SDPHeader, SDPFlag
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.impl import CheckOKResponse
from spinn_front_end_common.utilities.constants import (
    SDP_RUNNING_MESSAGE_CODES)
import struct


class SCPUpdateRuntimeRequest(AbstractSCPRequest):

    def __init__(
            self, x, y, p, current_time, run_time, infinite_run,
            destination_port, expect_response=True):
        # pylint: disable=too-many-arguments
        sdp_flags = SDPFlag.REPLY_NOT_EXPECTED
        if expect_response:
            sdp_flags = SDPFlag.REPLY_EXPECTED

        super(SCPUpdateRuntimeRequest, self).__init__(
            SDPHeader(
                flags=sdp_flags, destination_port=destination_port,
                destination_cpu=p, destination_chip_x=x, destination_chip_y=y),
            SCPRequestHeader(
                command=SDP_RUNNING_MESSAGE_CODES.SDP_NEW_RUNTIME_ID_CODE),
            argument_1=run_time, argument_2=infinite_run,
            argument_3=current_time,
            data=struct.pack("<B", int(bool(expect_response))))

    def get_scp_response(self):
        return CheckOKResponse(
            "update runtime",
            SDP_RUNNING_MESSAGE_CODES.SDP_NEW_RUNTIME_ID_CODE.value)
