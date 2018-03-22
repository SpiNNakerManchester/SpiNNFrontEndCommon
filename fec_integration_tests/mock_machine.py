from spinnman.messages.sdp import SDPMessage, SDPHeader, SDPFlag
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.enums import SCPResult
from spinnman.connections.udp_packet_connections import utils
from spinnman.connections.udp_packet_connections import UDPConnection

from threading import Thread
from collections import deque
import struct
import traceback


class _SCPOKMessage(SDPMessage):

    def __init__(self, x, y):
        scp_header = SCPRequestHeader(command=SCPResult.RC_OK)
        sdp_header = SDPHeader(
            flags=SDPFlag.REPLY_NOT_EXPECTED, destination_port=0,
            destination_cpu=0, destination_chip_x=x, destination_chip_y=y)
        utils.update_sdp_header_for_udp_send(sdp_header, 0, 0)
        super(_SCPOKMessage, self).__init__(
            sdp_header, data=scp_header.bytestring)


class MockMachine(Thread):
    """ A Machine that can be used for testing protocol
    """

    def __init__(self, responses=None):
        """
        :param responses:\
            An optional list of responses to send in the order to be sent. \
            If not specified, OK responses will be sent for every request. \
            Note that responses can include "None" which means that no\
            response will be sent to that request
        """
        super(MockMachine, self).__init__()

        # Set up a connection to be the machine
        self._receiver = UDPConnection()
        self._running = False
        self._messages = deque()
        self._error = None
        self._responses = deque()
        if responses is not None:
            self._responses.extend(responses)

    @property
    def is_next_message(self):
        return len(self._messages) > 0

    @property
    def next_message(self):
        return self._messages.popleft()

    @property
    def error(self):
        return self._error

    @property
    def local_port(self):
        return self._receiver.local_port

    def _do_receive(self):
        data, address = self._receiver.receive_with_address()
        self._messages.append(data)
        sdp_header = SDPHeader.from_bytestring(data, 2)
        response = None
        if self._responses:
            response = self._responses.popleft()
        else:
            response = _SCPOKMessage(
                sdp_header.source_chip_x, sdp_header.source_chip_y)
        if response is not None:
            self._receiver.send_to(
                struct.pack("<2x") + response.bytestring, address)

    def run(self):
        self._running = True
        while self._running:
            try:
                if self._receiver.is_ready_to_receive(10):
                    self._do_receive()
            except Exception as e:
                if self._running:
                    traceback.print_exc()
                    self._error = e

    def stop(self):
        self._running = False
        self._receiver.close()
