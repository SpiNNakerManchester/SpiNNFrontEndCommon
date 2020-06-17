# Copyright (c) 2017-2019 The University of Manchester
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
from datetime import datetime
from enum import IntEnum
import os
import re
import socket
import struct
from tools.scp import SCP


def _word(a, b, c, d):
    """
    Assembles a word out of four bytes.

    aaaaaaaa------------------------   << 24
    --------bbbbbbbb----------------   << 16
    ----------------cccccccc--------   <<  8
    ------------------------dddddddd   <<  0
    """
    return (
        (a & 0xFF) << 24) | ((b & 0xFF) << 16) | ((c & 0xFF) << 8) | (d & 0xFF)


# -----------------------------------------------------------------------------


class SCP_CMD(IntEnum):
    VER = 0
    RUN = 1
    READ = 2
    WRITE = 3
    FILL = 5

    LINK_READ = 17
    LINK_WRITE = 18

    LED = 25
    IPTAG = 26

    # Tubotron message
    TUBE = 64


class SCAMP_CMD(IntEnum):
    # SCAMP only
    APLX = 4
    REMAP = 16
    AR = 19
    NNP = 20
    P2PC = 21
    SIG = 22
    FFD = 23
    AS = 24
    SROM = 27
    ALLOC = 28
    RTR = 29
    INFO = 31


class BMP_CMD(IntEnum):
    # BMP only
    FLASH_COPY = 49
    FLASH_ERASE = 50
    FLASH_WRITE = 51
    BMP_SF = 53
    BMP_EE = 54
    RESET = 55
    POWER = 57


class TYPE(IntEnum):
    BYTE = 0
    HALF = 1
    WORD = 2


class NN_CMD(IntEnum):
    FFS = 6
    FFE = 15


Mem_type = {"byte": 0, "half": 1, "word": 2}


class IPTAG(IntEnum):
    NEW = 0
    SET = 1
    GET = 2
    CLR = 3
    TTO = 4
    UDP = 5

# -----------------------------------------------------------------------------


class Cmd(SCP):
    __slots__ = ()

    def _chunk(self, data, chunk_size=None):
        chunk_size = self._buf_size if chunk_size is None else chunk_size
        offset = 0
        while True:
            chunk = data[offset:offset + chunk_size]
            if not chunk:
                break
            yield chunk
            offset += len(chunk)

    # -------------------------------------------------------------------------

    def ver(self, raw=False, **kwargs):
        data = self.scp_cmd(SCP_CMD.VER, **kwargs)
        vc, pc, cy, cx, size, ver_num, timestamp = struct.unpack_from(
            "<4B 2H I", data)
        ver_str = data[12:]

        # Trim stuff after NUL byte; keep following material in case...
        ver_str, _, vn = ver_str.partition(b'\0')
        if ver_num != 0xFFFF:  # If an old style version number...
            if raw:
                return vc, pc, cy, cx, size, ver_num, timestamp, ver_str
            ver_num = "{:02f}".format(ver_num / 100)
        else:  # New style version number (three part)
            # Trim stuff after first NUL byte
            ver_num = vn.partition(b'\0')[0]
            if raw:
                m = re.match(r"(\d+)\.(\d+)\.(\d+)", ver_num)
                d1, d2, d3 = map(int, m.groups())
                vn = (d1 << 16) | (d2 << 8) | d3
                return vc, pc, cy, cx, size, vn, timestamp, ver_str

        name, hw = ver_str.split("/")
        timestamp = datetime.fromtimestamp(timestamp)
        return "{} {} at {}:{},{},{} (built {}) [{}]".format(
            name, ver_num, hw, cx, cy, vc, timestamp.isoformat(), pc)

    # -------------------------------------------------------------------------

    def _decode(self, data, unpack):
        if unpack:
            # Important! Some use cases have more data than we unpack
            data = struct.unpack_from(unpack, data)
        return data

    def read(self, base, length, unpack=None,
             type="byte",  # pylint: disable=redefined-builtin
             **kwargs):
        data = b''
        if type not in Mem_type:
            raise ValueError("bad memory type")
        if type == "word" and base & 3:
            raise ValueError("misaligned address")
        if type == "half" and base & 1:
            raise ValueError("misaligned address")
        type = Mem_type[type]  # @ReservedAssignment

        while length:
            _l = min(self._buf_size, length)
            data += self.scp_cmd(
                SCP_CMD.READ, arg1=base, arg2=_l, arg3=type, **kwargs)
            length -= _l
            base += _l

        return self._decode(data, unpack)

    def link_read(self, link, base, length, unpack=None, **kwargs):
        if not 0 <= link <= 5:
            raise ValueError("bad link")

        data = b''
        length = (length + 3) & ~3  # Round up to whole words
        while length:
            _l = min(self._buf_size, length)
            data += self.scp_cmd(
                SCP_CMD.LINK_READ, arg1=base, arg2=_l, arg3=link, **kwargs)
            length -= _l
            base += _l

        return self._decode(data, unpack)

    # -------------------------------------------------------------------------

    def write_file(self, base, filename, **kwargs):
        SIZE = 4096
        with open(filename, "rb") as f:
            # Determine the type
            size = os.fstat(f.fileno()).st_size
            if size & 1 or base & 1:
                ty = "byte"
            elif size & 2 or base & 2:
                ty = "half"
            else:
                ty = "word"

            while True:
                data = f.read(SIZE)
                if not data:
                    break
                self.write(base, data, type=ty, **kwargs)
                base += len(data)

    def write(self, base, data,
              type="byte",  # pylint: disable=redefined-builtin
              **kwargs):
        if type not in Mem_type:
            raise ValueError("bad memory type")
        if type == "word" and base & 3:
            raise ValueError("misaligned address")
        if type == "half" and base & 1:
            raise ValueError("misaligned address")
        type = Mem_type[type]  # @ReservedAssignment

        for buf in self._chunk(data):
            self.scp_cmd(SCP_CMD.WRITE, arg1=base, arg2=len(buf), arg3=type,
                         data=buf, **kwargs)
            base += len(buf)

    def link_write(self, link, base, data, **kwargs):
        if not 0 <= link <= 5:
            raise ValueError("bad link")
        while len(data) & 3:
            data += b'\0'

        for buf in self._chunk(data):
            length = len(buf)
            self.scp_cmd(SCP_CMD.LINK_WRITE, arg1=base, arg2=length, arg3=link,
                         data=buf, **kwargs)
            base += length

    # -------------------------------------------------------------------------

    def led(self, leds, **kwargs):
        self.scp_cmd(SCP_CMD.LED, arg1=leds, arg2=1 << self._c, **kwargs)

    # -------------------------------------------------------------------------

    def fill(self, base, data, length, **kwargs):
        if base & 3:
            raise ValueError("address not multiple of 4")
        if length & 3:
            raise ValueError("length not a multiple of 4")
        if length <= 0:
            raise ValueError("length not positive")

        self.scp_cmd(SCP_CMD.FILL, arg1=base, arg2=data, arg3=length, **kwargs)

    # -------------------------------------------------------------------------

    def iptag_set(self, tag, port, host="", dest_addr=0, dest_port=0,
                  reverse=False, strip=False, **kwargs):
        if reverse:
            strip = True
        flag = (reverse << 1) | strip
        ip = 0
        if host:
            if host == ".":
                host = self._host_ip
            # YUCK! Reassemble correct encoded form
            ip = sum(j << (8 * i) for i, j in enumerate(map(
                int, socket.gethostbyname(host).split("."))))
        arg1 = (flag << 28) | (IPTAG.SET << 16) | (dest_port << 8) | tag
        arg2 = (dest_addr << 16) | port
        self.scp_cmd(SCP_CMD.IPTAG, arg1=arg1, arg2=arg2, arg3=ip, **kwargs)

    def iptag_clear(self, tag, **kwargs):
        self.scp_cmd(SCP_CMD.IPTAG, arg1=(IPTAG.CLR << 16) | tag, **kwargs)

    def iptag_get(self, tag, count, **kwargs):
        return self.scp_cmd(SCP_CMD.IPTAG, arg1=(IPTAG.GET << 16) | tag,
                            arg2=count, **kwargs)

    def iptag_tto(self, tto, **kwargs):
        return self.scp_cmd(SCP_CMD.IPTAG, arg1=IPTAG.TTO << 16, arg2=tto,
                            **kwargs)

# -------------------------------------------------------------------------


class SCAMPCmd(Cmd):
    """ SCAMP-specific operations
    """
    # pylint: disable=redefined-builtin
    __slots__ = ("_nn_id", )

    def __init__(self, *args, **kwargs):
        """
        The following options are allowed

        target  - the target host name or IP. If omitted, a listening socket is
                  created
        port    - the UDP port to use (defaults to 17893 which is OK for
                  sending)
        timeout - the timeout to use when waiting for reply packets
        retries - the number of retries to use when the target doesn't respond
        debug   - a debug value (integers>0 cause debug output; defaults to 0)
        delay   - delay (seconds) before sending (to throttle packets)
        """
        super(SCAMPCmd, self).__init__(self, *args, **kwargs)
        self._nn_id = 0

    def _next_id(self):
        next_id = (self._nn_id % 127) + 1
        self._nn_id = next_id
        return next_id * 2

    # -------------------------------------------------------------------------

    def rtr_alloc(self, app_id, size, **kwargs):
        alloc_op = 3  # ALLOC_RTR
        base_entry_id, = self.scp_cmd(
            SCAMP_CMD.ALLOC, arg1=(app_id << 8) + alloc_op, arg2=size,
            unpack="<I", **kwargs)
        return base_entry_id

    def rtr_init(self, **kwargs):
        rtr_op = 0  # RTR_INIT
        self.scp_cmd(SCAMP_CMD.RTR, arg1=rtr_op, **kwargs)

    def rtr_clear(self, start, count, **kwargs):
        rtr_op = 1  # RTR_CLEAR
        self.scp_cmd(
            SCAMP_CMD.RTR, arg1=(count << 16) | rtr_op, arg2=start, **kwargs)

    def rtr_load(self, app_id, mem_addr, size, base_entry_id, **kwargs):
        rtr_op = 2  # RTR_MC_LOAD
        self.scp_cmd(
            SCAMP_CMD.RTR, arg1=(size << 16) | (app_id << 8) | rtr_op,
            arg2=mem_addr, arg3=base_entry_id, **kwargs)

    def rtr_fr_get(self, **kwargs):
        rtr_op = 3  # RTR_FR
        route, = self.scp_cmd(
            SCAMP_CMD.RTR, arg1=rtr_op, arg2=-1, unpack="<I", **kwargs)
        return route

    def rtr_fr_set(self, route, **kwargs):
        if route & (1 << 31):
            raise ValueError("route must not have top bit set")
        rtr_op = 3  # RTR_FR
        self.scp_cmd(SCAMP_CMD.RTR, arg1=rtr_op, arg2=route, **kwargs)

    # -------------------------------------------------------------------------

    def remap(self, proc_id, proc_id_is_physical=False, **kwargs):
        self.scp_cmd(
            SCAMP_CMD.REMAP, arg1=proc_id, arg2=proc_id_is_physical, **kwargs)

    # -------------------------------------------------------------------------

    def astart(self, base, mask, app_id, app_flags, **kwargs):
        arg = (app_id << 24) | (app_flags << 18) | mask
        self.scp_cmd(SCAMP_CMD.AS, arg1=base, arg2=arg, **kwargs)

    def ar(self, mask, app_id, app_flags, **kwargs):
        arg = (app_id << 24) | (app_flags << 18) | mask
        self.scp_cmd(SCAMP_CMD.AR, arg1=arg, **kwargs)

    def signal(self, type, data, mask, **kwargs):  # @ReservedAssignment
        return self.scp_cmd(
            SCAMP_CMD.SIG, arg1=type, arg2=data, arg3=mask, **kwargs)

    def p2pc(self, x, y, **kwargs):
        _id = self._next_id()
        arg1 = _word(0, 0x3E, 0, _id)
        arg2 = _word(x, y, 0, 0)
        arg3 = _word(0, 0, 0x3F, 0xF8)
        self.scp_cmd(SCAMP_CMD.P2PC, arg1=arg1, arg2=arg2, arg3=arg3,
                     addr=[], **kwargs)

    def nnp(self, arg1, arg2, arg3, **kwargs):
        self.scp_cmd(SCAMP_CMD.NNP, arg1=arg1, arg2=arg2, arg3=arg3, **kwargs)

    # -------------------------------------------------------------------------

    def srom_read(self, base, length, unpack=None, addr_size=24, **kwargs):
        data = b""
        while length:
            _l = min(length, self._buf_size)
            data += self.scp_cmd(
                SCAMP_CMD.SROM, arg1=(_l << 16) | addr_size | 8,
                arg2=0x03000000 + (base << (24 - addr_size)),
                **kwargs)
            length -= _l
            base += _l

        return self._decode(data, unpack)

    def srom_write(self, base, data, page_size=256, addr_size=24, **kwargs):
        for buf in self._chunk(data, page_size):
            length = len(buf)
            self.scp_cmd(
                SCAMP_CMD.SROM, arg1=(length << 16) + 0x1C0 + addr_size + 8,
                arg2=0x02000000 + (base << (24 - addr_size)), data=buf,
                **kwargs)
            base += length

    def srom_erase(self, **kwargs):
        self.scp_cmd(SCAMP_CMD.SROM, arg1=0xC8, arg2=0xC7000000, **kwargs)

    # -------------------------------------------------------------------------

    def flood_fill(self, buf, region, mask, app_id, app_flags, base=0x67800000,
                   **kwargs):
        size = len(buf)
        blocks = size // 256
        if size % 256:
            blocks += 1
        if self._debug:
            print("# FF {} bytes, {} blocks".format(size, blocks))

        sfwd, srty = 0x3F, 0x18         # Forward, retry parameters
        _id = self._next_id()           # ID for FF packets
        fr = _word(0, 0, sfwd, srty)    # Pack up fwd, rty
        sfr = (1 << 31) | fr            # Bit 31 says allocate ID on Spin

        # Send FFS packet
        key = _word(NN_CMD.FFS, _id, blocks, 0)
        data = region
        if self._debug:
            print("FFS {:08x} {:08x} {:08x}".format(key, data, sfr))
        self.nnp(key, data, sfr, **kwargs)

        # Send FFD data blocks
        for block, data in enumerate(self._chunk(buf, 256)):
            arg1 = _word(sfwd, srty, 0, _id)
            arg2 = _word(0, block, (len(data) // 4) - 1, 0)
            if self._debug:
                print("FFD {:08x} {:08x} {:08x}".format(arg1, arg2, base))
            self.scp_cmd(SCAMP_CMD.FFD, arg1=arg1, arg2=arg2, arg3=base,
                         data=data, **kwargs)
            base += len(data)

        # Send FFE packet
        key = _word(NN_CMD.FFE, 0, 0, _id)
        data = (app_id << 24) | (app_flags << 18) | (mask & 0x3FFFF)
        if self._debug:
            print("FFE {:08x} {:08x} {:08x}".format(key, data, fr))
        self.nnp(key, data, fr, **kwargs)

    def flood_boot(self, buf, **kwargs):
        size = len(buf)
        blocks = size // 256
        if size % 256:
            blocks += 1
        if self._debug:
            print("# FF Boot - {} bytes, {} blocks".format(size, blocks))

        sfwd, srty = 0x3F, 0x18
        nnp, ffd = SCAMP_CMD.NNP - 8, SCAMP_CMD.FFD - 8  # <<< WAT
        base, mask = 0xF5000000, 1
        fr = _word(0, 0, sfwd, srty)

        _id = self._next_id()

        # Send FFS packet (buffer address in data field)
        key = _word(NN_CMD.FFS, 0, blocks, _id)
        if self._debug:
            print("FFS {:08x} {:08x} {:08x}".format(key, base, fr))
        self.scp_cmd(nnp, arg1=key, arg2=base, arg3=fr, addr=[], *kwargs)

        # Send FFD data blocks
        for block, data in enumerate(self._chunk(buf, 256)):
            arg1 = _word(sfwd, srty, 0, _id)
            arg2 = _word(0, block, (len(data) // 4) - 1, 0)
            if self._debug:
                print("FFD {:08x} {:08x} {:08x}".format(arg1, arg2, base))
            self.scp_cmd(ffd, arg1=arg1, arg2=arg2, arg3=base, data=data,
                         addr=[], **kwargs)
            base += len(data)

        # Send FFE packet (mask (= 1) in data field)
        key = _word(NN_CMD.FFE, 0, 0, _id)
        if self._debug:
            print("FFS {:08x} {:08x} {:08x}".format(key, mask, fr))
        self.scp_cmd(nnp, arg1=key, arg2=mask, arg3=fr, addr=[], **kwargs)


# -------------------------------------------------------------------------


class BMPCmd(Cmd):
    """ BMP-specific operations
    """
    __slots__ = ()

    def sf_read(self, base, length, **kwargs):
        data = b''
        while length:
            _l = min(length, self._buf_size)
            data += self.scp_cmd(BMP_CMD.BMP_SF, arg1=base, arg2=_l, arg3=0,
                                 **kwargs)
            length -= _l
            base += _l
        return data

    def sf_write(self, base, data, **kwargs):
        for buf in self._chunk(data):
            self.scp_cmd(BMP_CMD.BMP_SF, arg1=base, arg2=len(buf), arg3=1,
                         data=buf, **kwargs)
            base += len(buf)

    def flash_write(self, addr, data, update=False, **kwargs):
        size = len(data)
        if not size:
            raise ValueError("no data")
        if addr & 4095:
            raise ValueError("not on 4kB boundary")
        if addr < 65536 and addr + size > 65536:
            raise ValueError("crosses flash 4k/32k boundary")
        if addr + size > 524288:
            raise ValueError("address not in flash")

        # Erase and get address of flash buffer
        flash_buf, = self.scp_cmd(
            BMP_CMD.FLASH_ERASE, arg1=addr, arg2=addr+size,
            unpack="<I", **kwargs)

        # Write as many times as needed
        base = addr
        for buf in self._chunk(data, 4096):
            self.write(flash_buf, buf)
            self.scp_cmd(BMP_CMD.FLASH_WRITE, arg1=base, arg2=4096, **kwargs)
            base += 4096

        # Update if requested
        if update:
            self.scp_cmd(
                BMP_CMD.FLASH_COPY, arg1=0x10000, arg2=addr, arg3=size,
                **kwargs)

    def reset(self, mask, delay=0, **kwargs):
        self.scp_cmd(
            BMP_CMD.RESET, arg1=(delay << 16) | 6, arg2=mask, **kwargs)

    def power(self, on, mask, delay=0, **kwargs):
        self.scp_cmd(
            BMP_CMD.POWER, arg1=(delay << 16) | on, arg2=mask,
            timeout=(5.0 if on else self._timeout), **kwargs)
