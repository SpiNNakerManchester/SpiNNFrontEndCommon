from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.abstract_messages import (
    AbstractSCPRequest, AbstractSCPResponse)
from spinnman.messages.scp.enums import SCPResult
from spinnman.messages.sdp import SDPFlag, SDPHeader
from spinnman.exceptions import SpinnmanUnexpectedResponseCodeException
from spinn_front_end_common.utilities.utility_objs import ReInjectionStatus
from spinn_front_end_common.utilities import constants
from .reinjector_scp_commands import ReinjectorSCPCommands


class GetReinjectionStatusMessage(AbstractSCPRequest):
    """ An SCP Request to get the status of the dropped packet reinjection
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

        super(GetReinjectionStatusMessage, self).__init__(
            SDPHeader(
                flags=SDPFlag.REPLY_EXPECTED,
                destination_port=(
                    constants.SDP_PORTS.EXTRA_MONITOR_CORE_REINJECTION.value),
                destination_cpu=p, destination_chip_x=x,
                destination_chip_y=y),
            SCPRequestHeader(command=ReinjectorSCPCommands.GET_STATUS))

    def get_scp_response(self):
        return GetReinjectionStatusMessageResponse(
            ReinjectorSCPCommands.GET_STATUS)


class GetReinjectionStatusMessageResponse(AbstractSCPResponse):
    """ An SCP response to a request for the dropped packet reinjection status
    """

    def __init__(self, command_code):
        super(GetReinjectionStatusMessageResponse, self).__init__()
        self._reinjection_functionality_status = None
        self._command_code = command_code

    def read_data_bytestring(self, data, offset):
        """ See\
            :py:meth:`spinnman.messages.scp.abstract_scp_response.AbstractSCPResponse.read_data_bytestring`
        """
        result = self.scp_response_header.result
        if result != SCPResult.RC_OK:
            raise SpinnmanUnexpectedResponseCodeException(
                "Get packet reinjection status", self._command_code,
                result.name)
        self._reinjection_functionality_status = \
            ReInjectionStatus(data, offset)

    @property
    def reinjection_functionality_status(self):
        return self._reinjection_functionality_status
