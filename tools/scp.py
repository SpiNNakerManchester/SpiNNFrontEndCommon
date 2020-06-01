# Copyright (c) 2013-2020 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import inspect
import select
import socket
import struct
import time
from tools.util import hex_dump
from tools.exn import SpinnException, SpinnTooManyRetriesException

SPIN_PORT = 17893
TIMEOUT = 0.5
RETRIES = 2
MAX_CORE = 31

RC_OK = 0x80

RC = {
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
    __slots__ = ("__socket", "_port", "_target_name", "_target_ip", "_host_ip",
                 "_timeout", "_retries", "_debug", "_delay", "_buf_size",
                 "_tx_seq", "_rx_seq", "_cmd_rc", "_x", "_y", "_c",
                 "_tag", "_flags", "_sa", "_sp", "_sdp_hdr", "_sdp_data")

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
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if target:
            self.__socket.connect((target, port))
        else:
            self.__socket.bind(("", port))

        self._port = port
        self._target_name = target
        self._target_ip = \
            self.__socket.getpeername()[0] if target else "x.x.x.x"
        self._host_ip = self.__socket.getsockname()[0]

        self._timeout = float(timeout)
        self._retries = int(retries)
        self._debug = int(debug)
        self._delay = int(delay)

        self._buf_size = 256
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

    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------

    def send_sdp(self, data, addr=None, port=0, reply=False, debug=None,
                 delay=None):
        """
        Send a packet containing SDP data to a SpiNNaker machine. The default
        address (chip/core) is used unless it is overridden. An SDP header is
        constructed and prepended to the data which is then sent in a single
        UDP packet. The following options are possible

        addr  - specifies an address to override the default. A list
                containing up to three args (see "addr" above for spec.)
        port  - a 3 bit port number to be used at the destination (default 0)
        reply - must be set True if a reply is expected from the destination
        delay - delay in seconds before each send (for throttling)
        """
        debug = self._debug if debug is None else debug
        delay = self._delay if delay is None else delay
        if len(data) > self._buf_size + 16:
            raise ValueError("SDP data overflow")
        x, y, c = self._x, self._y, self._c
        if addr is not None:
            if len(addr) == 0:
                x, y, c = 255, 255, 0
            elif len(addr) == 1:
                c = addr[0]
            elif len(addr) == 2:
                x, y = addr
                c = 0
            elif len(addr) == 3:
                x, y, c = addr
            else:
                raise ValueError("bad address")
        if not 0 <= x <= 255 or not 0 <= y <= 255:
            raise ValueError("bad address")
        if not 0 <= c <= MAX_CORE:
            raise ValueError("bad core number")

        da = (x << 8) | y
        dp = (port << 5) | c
        flags = self._flags
        if reply:
            flags |= 0x80

        pad = struct.pack("<H", 0)
        hdr = struct.pack("<4B2H", flags, self._tag, dp, self._sp, da, self._sa)
        if delay:
            time.sleep(delay)
        self.__socket.send(pad + hdr + data)
        if debug >= 3:
            print(self._sdp_dump(
                hdr, data, prefix="#>SDP ", print_data=debug>=4))

    def send_scp(self, cmd, arg1, arg2, arg3, data, debug=None, **kwargs):
        """
        Send a packet containing SCP data to a SpiNNaker machine (uses
        "send_sdp"). A command and three arguments must be supplied and these
        are packed along with the data before being sent with "send_sdp". A
        sequence number is inserted which is kept in the class data. The same
        options as for "send_sdp" may be provided (addr, retry, port, delay).
        """
        debug = self._debug if debug is None else debug
        if len(data) > self._buf_size:
            raise ValueError("SCP data overflow")

        scp_hdr = struct.pack("<2H 3I", cmd, self._tx_seq, arg1, arg2, arg3)
        if debug:
            print(self._scp_dump(scp_hdr, num_args=3, prefix="#>SCP ",
                                 print_data=debug >= 2))
        self.send_sdp(scp_hdr + data, debug=debug, **kwargs)

    def recv_sdp(self, timeout=None, debug=None):
        """
        Receive a packet containing SDP data. Waits for a timeout which is
        taken from the class data unless overridden by an option. Returns
        False if the receive times out otherwise True; The SDP header and data
        are saved in the class data.

        timeout - timeout for reception (overrides class data default)
        """
        timeout = self._timeout if timeout is None else timeout
        debug = self._debug if debug is None else debug

        self._sdp_hdr = b''
        ready = select.select([self.__socket], [], [], timeout)
        if not ready:
            return False
        buf = self.__socket.recv(65536)
        if len(buf) < 10:
            raise RuntimeError("malformed SDP header")
        self._sdp_hdr = buf[2:10]
        self._sdp_data = buf[10:]

        if debug >= 3:
            print(self._sdp_dump(self._sdp_hdr, self._sdp_data, prefix="#<SDP ",
                                 print_data=debug >= 4))
        return True

    def recv_scp(self, timeout=None, debug=None):
        """
        Receive a packet containing SCP data. Waits for a timeout which is
        taken from the class data unless overridden by an option. Returns
        None if the receive times out otherwise the "cmd_rc" field from
        the packet
        """
        timeout = self._timeout if timeout is None else timeout
        debug = self._debug if debug is None else debug

        if not self.recv_sdp(timeout, debug):
            return None
        if len(self._sdp_data) < 4:
            raise RuntimeError("malformed SCP packet")
        self._cmd_rc, self._rx_seq = struct.unpack_from("<2H", self._sdp_data)

        if debug:
            print(self._scp_dump(self._sdp_data, prefix="#<SCP ",
                                 print_data=debug >= 2))
        return self._cmd_rc

    def scp_cmd(self, cmd, arg1=0, arg2=0, arg3=0, data=b'', addr=None, port=0,
                unpack=None, timeout=None, retries=None, debug=None):
        """
        Send a command to a Spinnaker target using SDP over UDP and receive
        a reply.

        Arguments: cmd options...

        Options:
            arg1 - argument 1
            arg2 - argument 2
            arg3 - argument 3
            data - data
            port (integer) SpiNNaker (3-bit) port
            addr ([]) chip/core address
            unpack - unpack format for returned data
            timeout - override default timeout
            retries - override default retries
            debug - set debug level

        Returns: data (possibly unpacked)
        """
        timeout = self._timeout if timeout is None else timeout
        retries = self._retries if retries is None else retries
        debug = self._debug if debug is None else debug

        self._tx_seq = (self._tx_seq + 1) & 0xFFFF

        for tries in range(retries):
            self.send_scp(cmd, arg1, arg2, arg3, data, debug=debug, addr=addr,
                          port=port, reply=True)
            rc = self.recv_scp(timeout, debug)
            if self._rx_seq != self._tx_seq:
                # Skip unexpected crossed reply
                continue
            if rc is not None:
                break
            if debug:
                print("# Timeout (attempt {})".format(tries + 1))
        else:
            raise SpinnTooManyRetriesException("too many retries")
        if rc != RC_OK:
            raise SpinnException("error {}".format(
                RC[rc] if rc in RC else "0x{:02x}".format(rc)))

        if unpack:
            return struct.unpack(unpack, self._sdp_data[4:])
        return self._sdp_data[4:]

    # -------------------------------------------------------------------------

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, timeout):
        self._timeout = float(timeout)

    @property
    def debug(self):
        return self._debug

    @debug.setter
    def debug(self, debug):
        self._debug = int(debug)

    @property
    def flags(self):
        return self._flags

    @flags.setter
    def flags(self, flags):
        self._flags = int(flags)

    @property
    def retries(self):
        return self._retries

    @retries.setter
    def retries(self, retries):
        self._retries = int(retries)

    # -------------------------------------------------------------------------

    def close(self):
        self.__socket.close()
        self.__socket = None

    def dump_self(self):
        for name, value in inspect.getmembers(
                self, lambda obj: not inspect.isroutine(obj)):
            if name.startswith("_") and not name.startswith("__"):
                print("{:-16s} {}".format(name.strip("_"), value))
