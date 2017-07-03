from spinnman.messages.sdp import SDPHeader, SDPFlag
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.impl import CheckOKResponse
from spinn_front_end_common.utilities.constants \
    import SDP_RUNNING_MESSAGE_CODES


class SCPUpdateRuntimeRequest(AbstractSCPRequest):

    def __init__(
            self, x, y, p, run_time, infinite_run, destination_port,
            expect_response=True):
        sdp_flags = SDPFlag.REPLY_NOT_EXPECTED
        arg3 = 0
        if expect_response:
            sdp_flags = SDPFlag.REPLY_EXPECTED
            arg3 = 1

        AbstractSCPRequest.__init__(
            self,
            SDPHeader(
                flags=sdp_flags, destination_port=destination_port,
                destination_cpu=p, destination_chip_x=x, destination_chip_y=y),
            SCPRequestHeader(
                command=SDP_RUNNING_MESSAGE_CODES.SDP_NEW_RUNTIME_ID_CODE),
            argument_1=run_time, argument_2=infinite_run, argument_3=arg3)

    def get_scp_response(self):
        return CheckOKResponse(
            "update runtime",
            SDP_RUNNING_MESSAGE_CODES.SDP_NEW_RUNTIME_ID_CODE.value)
