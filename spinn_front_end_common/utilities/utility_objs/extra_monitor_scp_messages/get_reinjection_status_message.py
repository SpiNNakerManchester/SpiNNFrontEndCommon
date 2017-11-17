from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.abstract_messages \
    import AbstractSCPRequest, AbstractSCPResponse
from spinnman.messages.scp.enums import SCPResult
from spinnman.messages.sdp import SDPFlag, SDPHeader
from spinnman.exceptions import SpinnmanUnexpectedResponseCodeException
from spinn_front_end_common.utilities.utility_objs.reinjection_status import \
    ReInjectionStatus
from spinn_front_end_common.utilities import constants


class GetReinjectionStatusMessage(AbstractSCPRequest):
    """ An SCP Request to get the status of the dropped packet reinjection
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
        vertex for getting reinjection status
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
            SCPRequestHeader(command=command_code))

    def get_scp_response(self):
        return GetReinjectionStatusMessageResponse(self._command_code)


class GetReinjectionStatusMessageResponse(AbstractSCPResponse):
    """ An SCP response to a request for the dropped packet reinjection status
    """

    def __init__(self, command_code):
        """
        """

        AbstractSCPResponse.__init__(self)
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
