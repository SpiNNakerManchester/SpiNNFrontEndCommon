from spinn_front_end_common.utility_models.\
    extra_monitor_support_machine_vertex import \
    ExtraMonitorSupportMachineVertex
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.abstract_messages \
    import AbstractSCPRequest, AbstractSCPResponse
from spinnman.messages.scp.enums import SCPResult
from spinnman.messages.sdp import SDPFlag, SDPHeader
from spinnman.exceptions import SpinnmanUnexpectedResponseCodeException
from spinn_front_end_common.utilities.utility_objs.re_injection_status import \
    ReInjectionStatus


class GetReinjectionStatusMessage(AbstractSCPRequest):
    """ An SCP Request to get the status of the dropped packet reinjection
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
            SCPRequestHeader(command=ExtraMonitorSupportMachineVertex.
                             EXTRA_MONITOR_COMMANDS.GET_STATUS.value()))

    def get_scp_response(self):
        return GetReinjectionStatusMessageResponse()


class GetReinjectionStatusMessageResponse(AbstractSCPResponse):
    """ An SCP response to a request for the dropped packet reinjection status
    """

    def __init__(self):
        """
        """
        AbstractSCPResponse.__init__(self)
        self._reinjection_functionality_status = None

    def read_data_bytestring(self, data, offset):
        """ See\
            :py:meth:`spinnman.messages.scp.abstract_scp_response.AbstractSCPResponse.read_data_bytestring`
        """
        result = self.scp_response_header.result
        if result != SCPResult.RC_OK:
            raise SpinnmanUnexpectedResponseCodeException(
                "Get dropped packet reinjection status",
                ExtraMonitorSupportMachineVertex.EXTRA_MONITOR_COMMANDS.
                GET_STATUS.value(), result.name)
        self._reinjection_functionality_status = \
            ReInjectionStatus(data, offset)

    @property
    def reinjection_functionality_status(self):
        return self._reinjection_functionality_status
