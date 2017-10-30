from spinn_front_end_common.utility_models.\
    extra_monitor_support_machine_vertex import \
    ExtraMonitorSupportMachineVertex
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.sdp import SDPFlag, SDPHeader
from spinnman.messages.scp.impl.check_ok_response import CheckOKResponse


class SetReinjectionPacketTypesMessage(AbstractSCPRequest):
    """ An SCP Request to set the dropped packet reinjected packet types
    """

    def __init__(self, x, y, p, packet_types):
        """
        :param x: The x-coordinate of a chip, between 0 and 255
        :type x: int
        :param y: The y-coordinate of a chip, between 0 and 255
        :type y: int
        :param p: The processor running the dropped packet reinjector, between\
                0 and 17
        :type p: int
        :param packet_types: The types of packet to reinject - if empty or\
                None reinjection is disabled
        :type packet_types: None or list of \
                `py:class:spinnman.messages.scp.scp_dpri_packet_type_flags.SCPDPRIPacketTypeFlags`
        """
        flags = 0
        if packet_types is not None:
            for packet_type in packet_types:
                flags |= packet_type.value

        AbstractSCPRequest.__init__(
            self,
            SDPHeader(
                flags=SDPFlag.REPLY_EXPECTED, destination_port=0,
                destination_cpu=p, destination_chip_x=x,
                destination_chip_y=y),
            SCPRequestHeader(command=ExtraMonitorSupportMachineVertex.
                             EXTRA_MONITOR_COMMANDS.SET_PACKET_TYPES.value()),
            argument_1=flags)

    def get_scp_response(self):
        return CheckOKResponse(
            "Set reinjected packet types",
            ExtraMonitorSupportMachineVertex.EXTRA_MONITOR_COMMANDS.
            SET_PACKET_TYPES.value())
