import socket
import struct
from tools.util import hex_dump

SPIN_PORT = 17893
TIMEOUT = 0.5
RETRIES = 2
MAX_CORE = 31

RC_OK = 0x80

rc = {
    0x80: "RC_OK",
    0x81: "RC_LEN",
    0x82: "RC_SUM",
    0x83: "RC_CMD",
    0x84: "RC_ARG",
    0x85: "RC_PORT",
    0x86: "RC_TIMEOUT",
    0x87: "RC_ROUTE",
    0x88: "RC_CPU",
    0x89: "RC_DEAD",
    0x8a: "RC_BUF",
    0x8b: "RC_P2P_NOREPLY",
    0x8c: "RC_P2P_REJECT",
    0x8d: "RC_P2P_BUSY",
    0x8e: "RC_P2P_TIMEOUT",
    0x8f: "RC_PKT_TX",
}


class SCP(object):
    """ Class implementing SpiNNaker SCP & SDP """

    def __init__(self, target="", port=SPIN_PORT, timeout=TIMEOUT,
                 retries=RETRIES, debug=0, delay=0.0):
        """
        The following options are allowed

        target  - the target host name or IP. If omitted, a listening socket is
                  created
        port    - the UDP port to use (defaults to 17893 which is OK for
                  sending)
        timeout - the timeout to use when waiting for reply packets
        retries - the number of retries to use when the target doesn't respond
        debug   - a debug value (integers > 0 cause debug output; defaults to 0)
        delay   - delay (seconds) before sending (to throttle packets)
        """
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if target:
            self._socket.connect((target, port))
        else:
            self._socket.bind(("", port))

        self._port = port
        self._target_name = target
        self._target_ip = self._socket.getpeername()[0] if target else "x.x.x.x"
        self._host_ip = self._socket.getsockname()[0]

        self._timeout = timeout
        self._retries = retries
        self._debug = debug
        self._delay = delay

        self._buf_size = 256
        self._nn_id = 0
        self._tx_seq = 0
        self._rx_seq = 0
        self._cmd_rc = 0
        self._x = 0
        self._y = 0
        self._c = 0

        self._tag = 255
        self._flags = 0x07
        self._sa = 0
        self._sp = 255

        self._sdp_hdr = b""
        self._sdp_data = b""

    def addr(self, *args):
        """
        Set the default chip/core address that the connection uses to talk to
        SpiNNaker. Up to three arguments can be given with the following
        effects:

        0 args - chip_x = 255, chip_y = 255, core = 0
        1 arg  - core = arg1 (chip_x, chip_y unchanged)
        2 args - chip_x = arg1, chip_y = arg2, core = 0
        3 args - chip_x = arg1, chip_y = arg2, core = arg3
        """
        if len(args) == 0:
            self._x, self._y, self._c = 255, 255, 0
        elif len(args) == 1:
            if not 0 <= args[0] <= MAX_CORE:
                raise ValueError("bad core number")
            self._c = args[0]
        elif len(args) == 2:
            self._x, self._y, self._c = args[0], args[1], 0
        elif len(args) == 3:
            if not 0 <= args[2] <= MAX_CORE:
                raise ValueError("bad core number")
            self._x, self._y, self._c = args
        else:
            raise ValueError("bad address")
        return self._x, self._y, self._c

    @staticmethod
    def _sdp_dump(hdr, body, prefix="#SDP ", print_data=0):
        text = prefix

        flags, tag, dp, sp, dy, dx, sy, sx = struct.unpack_from("<8B", hdr, 0)
        if sp > 31 and sp != 255:
            sp = "{:d}/{:d}".format(sp >> 5, sp & 31)
        elif sp == 255:
            sp = "Ether"
        else:
            sp = str(sp)
        if dp > 31 and dp != 255:
            dp = "{:d}/{:d}".format(dp >> 5, dp & 31)
        elif dp == 255:
            dp = "Ether"
        else:
            dp = str(dp)

        text += "Flag {:02x}  Tag {:3d}  ".format(flags, tag)
        text += "DA {},{}  DP {:5d}  SA {},{}  SP {:5d}".format(
            dx, dy, dp, sx, sy, sp)
        text += " [{}]\n".format(len(body))
        if print_data:
            text += hex_dump(body, prefix=prefix, do_print=False)
        return text

    @staticmethod
    def _scp_dump(data, num_args=0, prefix="#SCP ", print_data=False):
        cmd_rc, seq = struct.unpack_from("<2H", data)
        text = "{}Cmd_RC {:3d}  Seq {:5d}".format(prefix, cmd_rc, seq)
        offset = 4
        if num_args:
            args = struct.unpack_from("<{}V".format(num_args), data, offset)
            offset += 4 * num_args
            for i, arg in enumerate(args):
                text += "  Arg{} 0x{:08x}".format(i + 1, arg)
        text += " [{}]\n".format(len(data) - offset)
        if print_data and offset < len(data):
            text += hex_dump(data[offset:], prefix=prefix, do_print=False)
        return text
