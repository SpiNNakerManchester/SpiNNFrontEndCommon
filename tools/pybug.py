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
from collections import namedtuple
from datetime import datetime
from enum import IntEnum
import re
import struct
import sys
import time
from zlib import crc32
from spinn_front_end_common import __version__ as fec_version
from tools.exn import BadArgs, SpinnException, SpinnTooManyRetriesException
from tools.cli import CLI
from tools.boot import boot
from tools.sv import Struct
from tools.cmd import SCAMPCmd, BMPCmd, SCAMP_CMD
from tools.util import (
    read_file, hex_dump, parse_cores, parse_region, parse_apps, parse_bits)

# This code ought to be rewritten to use the Cmd package:
# https://docs.python.org/3.8/library/cmd.html

# ------------------------------------------------------------------------------

spin = None          # Cmd object for SpiNNaker
bmp = None           # Cmd object for BMP (or undef)
_cli = None          # CLI object

sv = None            # Struct object

debug = False        # Enable verbosity
expert = False       # Expert mode
_readline = True     # Use readline

spinn_target = None  # Target host name
bmp_target = None    # BMP host name

bmp_range = None     # BMP ID range

spin_port = 17893    # UDP port for SpiNNaker
bmp_port = 17893     # UDP port for BMP
TUBE_PORT = 17892    # UDP port for Tubotron

APP_MIN = 16         # Minimum user AppId
APP_MAX = 255        # Maximum AppId

MIN_TAG, MAX_TAG = 0, 7  # Hard-coded range

(chip_x, chip_y, cpu) = (0, 0, 0)

srom_type = "25aa1024"  # SROM type

# ------------------------------------------------------------------------------


class NN_CMD(IntEnum):
    SIG0 = 0
    SIG1 = 4


def parse_app_id(string):
    app_id = str(string, base=0)
    if not APP_MIN <= app_id <= APP_MAX:
        raise ValueError("bad App ID")
    return app_id


# ------------------------------------------------------------------------------


def cmd_boot(cli):
    if cli.count > 2:
        raise BadArgs
    filename = cli.arg(0) or "scamp.boot"
    conf = cli.arg(1) or ""

    try:
        # Warn if already booted
        try:
            spin.ver(addr=[], timeout=0.1)
            print("Warning: Already booted")
        except SpinnException:
            pass

        boot(spinn_target, filename, conf, debug=debug)

        # Wait for boot to complete
        booted = True
        have_waited = False
        while True:
            version_info = spin.ver(addr=[], raw=True)
            booted = version_info[3] != 0xFF and version_info[2] != 0xFF
            if booted:
                break
            print(".", end="")
            time.sleep(0.5)
            have_waited = True
        if have_waited:
            print("")

        # Inform the user!
        s = spin.ver(addr=[])
        s = re.sub(" at .*", "", s)

        n = sv.read_var("sv.p2p_active", addr=[])
        spin.iptag_set(0, TUBE_PORT, host="0.0.0.0", addr=[])

        print("Booted {} on {} chips".format(s, n))
    finally:
        # Return to the chip we were on before booting
        spin.addr(chip_x, chip_y, cpu)


def cmd_sver(cli):
    if cli.count:
        raise BadArgs
    print(spin.ver())


def cmd_lw(cli):
    if not 2 <= cli.count <= 3:
        raise BadArgs
    link = cli.arg_i(0)
    addr = cli.arg_i(1)

    if cli.count == 2:
        data, = spin.link_read(link, addr, 4, unpack="<I")
        print("{:08x} = {:08x}".format(addr, data))
    else:
        data = struct.pack("<I", cli.arg_i(2))
        spin.link_write(link, addr, data)


def cmd_lmemw(cli):
    if cli.count != 2:
        raise BadArgs
    link = cli.arg_i(0)
    addr = cli.arg_i(1)
    data = spin.link_read(link, addr, 256)
    hex_dump(data, addr=addr, format="word")


def cmd_smemw(cli):
    if cli.count > 1:
        raise BadArgs
    addr = cli.arg_i(0) if cli.count else 0
    data = spin.read(addr, 256, type="word")
    hex_dump(data, addr=addr, format="word")


def cmd_smemh(cli):
    if cli.count > 1:
        raise BadArgs
    addr = cli.arg_i(0) if cli.count else 0
    data = spin.read(addr, 256, type="half")
    hex_dump(data, addr=addr, format="half", width=16)


def cmd_smemb(cli):
    if cli.count > 1:
        raise BadArgs
    addr = cli.arg_i(0) if cli.count else 0
    data = spin.read(addr, 256, type="byte")
    hex_dump(data, addr=addr)


def cmd_sw(cli):
    if not 1 <= cli.count <= 2:
        raise BadArgs
    addr = cli.arg_i(0)
    if cli.count == 1:
        data, = spin.read(addr, 4, type="word", unpack="<I")
        print("{:08x} = {:08x}".format(addr, data))
    else:
        data = struct.pack("<I", cli.arg_i(1))
        spin.write(addr, data, type="word")


def cmd_sh(cli):
    if not 1 <= cli.count <= 2:
        raise BadArgs
    addr = cli.arg_i(0)
    if cli.count == 1:
        data, = spin.read(addr, 2, type="half", unpack="<H")
        print("{:08x} = {:04x}".format(addr, data))
    else:
        data = struct.pack("<H", cli.arg_i(1))
        spin.write(addr, data, type="half")


def cmd_sb(cli):
    if not 1 <= cli.count <= 2:
        raise BadArgs
    addr = cli.arg_i(0)
    if cli.count == 1:
        data, = spin.read(addr, 1, type="byte", unpack="<B")
        print("{:08x} = {:02x}".format(addr, data))
    else:
        data = struct.pack("<B", cli.arg_x(1))
        spin.write(addr, data, type="byte")


def cmd_sfill(cli):
    if cli.count != 3:
        raise BadArgs
    _from = cli.arg_i(0)
    to = cli.arg_i(1)
    spin.fill(_from, cli.arg_i(2), to - _from)


def cmd_sp(cli):
    global chip_x, chip_y, cpu
    if not cli.count or (cli.count == 1 and cli.arg(0) == "root"):
        # Try and determine the true coordinates of the root chip
        root_x, root_y = 0, 0
        try:
            version_info = spin.ver(addr=[], raw=1, timeout=0.1)
            root_x = version_info[3]
            root_y = version_info[2]
        except SpinnException:
            pass
        chip_x, chip_y, cpu = spin.addr(root_x, root_y)
    elif cli.count == 1:
        chip_x, chip_y, cpu = spin.addr(cli.arg_i(0))
    elif cli.count == 2:
        chip_x, chip_y, cpu = spin.addr(
            cli.arg_i(0), cli.arg_i(1))
    elif cli.count == 3:
        chip_x, chip_y, cpu = spin.addr(
            cli.arg_i(0), cli.arg_i(1), cli.arg_i(2))
    else:
        raise BadArgs

    # Update the prompt
    cli.prompt = re.sub(
        r":.+", ":{},{},{} > ".format(chip_x, chip_y, cpu), cli.prompt)


# ------------------------------------------------------------------------------


def _iodump(fh, buf):
    _next, _time, _ms, _len = struct.unpack_from("<IIII", buf)
    base = 16
    _string = buf[base:base + _len]
    fh.write(_string)
    return _next


def cmd_iobuf(cli):
    if not 1 <= cli.count <= 2:
        raise BadArgs
    core = cli.arg_i(0)

    opened = cli.count > 1
    if opened:
        fh = open(cli.arg(1))
    else:
        fh = sys.stdout

    try:
        vbase = sv.read_var("sv.vcpu_base")
        size = sv.read_var("sv.iobuf_size")
        vsize = sv.size("vcpu")

        sv.base("vcpu", vbase + vsize * core)

        iobuf = sv.read_var("vcpu.iobuf")
        while iobuf:
            data = spin.read(iobuf, size + 16)
            iobuf = _iodump(fh, data)
    finally:
        if opened:
            fh.close()


# ------------------------------------------------------------------------------


def dump_heap(heap, name):
    heap_free, heap_first, _, free_bytes = spin.read(heap, 16, unpack="<IIII")
    print("")
    print("{} {}".format(name, free_bytes))
    print("-" * len(name))

    p = heap_first
    while p:
        _next, free = spin.read(p, 8, unpack="<II")
        size = 0 if _next == 0 else _next - p - 8
        if free & 0xFFFF0000 == 0xFFFF0000:
            fs = "Tag {:3d} ID {:3d}".format(free & 0xFF, (free >> 8) & 0xFF)
        else:
            fs = "Free  {:08x}".format(free)
        print("BLOCK  {:8x}  Next {:8x}  {}  Size {}".format(
            p, _next, fs, size))
        p = _next

    p = heap_free
    while p:
        _next, free = spin.read(p, 8, unpack="<II")
        size = 0 if _next == 0 else _next - p - 8
        print("FREE   {:8x}  Next {:8x}  Free  {:08x}  Size {}".format(
            p, _next, free, size))
        p = free


def cmd_heap(cli):
    if cli.count > 1:
        raise BadArgs
    arg = cli.arg(0) if cli.count else None

    if arg is None or arg == "sdram":
        dump_heap(sv.read_var("sv.sdram_heap"), "SDRAM")
    if arg is None or arg == "sysram":
        dump_heap(sv.read_var("sv.sysram_heap"), "SysRAM")
    if arg is None or arg == "system":
        dump_heap(sv.read_var("sv.sys_heap"), "System")

    print("")


# ------------------------------------------------------------------------------


def cmd_rtr_load(cli):
    if cli.count != 2:
        raise BadArgs
    _file = cli.arg(0)
    app_id = parse_app_id(cli.arg(1))

    buf = read_file(_file, 65536)
    size = len(buf)
    if size % 16 or not 32 <= size <= 1024 * 16:
        raise ValueError("Funny file size: {}".format(size))
    size = (size - 16) % 16

    addr = 0x67800000
    spin.write(addr, buf)
    base = spin.scp_cmd(
        SCAMP_CMD.ALLOC, arg1=(app_id << 8) + 3, arg2=size, unpack="<I")
    if not base:
        raise RuntimeError("no room in router heap")
    spin.scp_cmd(SCAMP_CMD.RTR,
                 arg1=(size << 16) + (app_id << 8 + 2), arg2=addr, arg3=base)


# ------------------------------------------------------------------------------


def ipflag(flags):
    r = "T" if flags & 0x4000 else ""
    r += "A" if flags & 0x2000 else ""
    r += "R" if flags & 0x0200 else ""
    r += "S" if flags & 0x0100 else ""
    return r


def dump_iptag():
    tto, pool, fix = spin.iptag_tto(255, unpack="<BxBB")
    _max = pool + fix
    tto = (1 << (tto - 1)) / 100 if tto else 0

    print("IPTags={} (F={}, T={}), TTO={}s\n".format(_max, fix, pool, tto))
    print("Tag    IP address    TxPort RxPort  T/O   Flags    Addr    Port"
          "      Count")
    print("---    ----------    ------ ------  ---   -----    ----    ----"
          "      -----")

    for i in range(_max):
        (ip, _mac, tx_port, timeout, flags, count, rx_port, spin_addr,
         spin_port_id) = spin.iptag_get(i, True, unpack="<4s6sHHHIHHB")
        if flags & 0x8000:  # Tag in use
            print(
                "{:3d}  {:<15s}  {:5d}  {:5d}  {:<4s}  {:<4s}   0x{:04x}    "
                "0x{:02x} {:10d}".format(
                    i, ".".join(map(str, struct.unpack("BBBB", ip))),
                    tx_port, rx_port, timeout / 100, ipflag(flags), spin_addr,
                    spin_port_id, count))


def cmd_iptag(cli):
    if not cli.count:
        dump_iptag()
        return
    if cli.count < 2:
        raise BadArgs

    tag = cli.arg_i(0)
    if not MIN_TAG <= tag <= MAX_TAG:
        raise ValueError("bad tag")
    command = cli.arg(1)

    if command == "clear":
        if cli.count != 2:
            raise BadArgs
        spin.iptag_clear(tag)
    elif command in ("set", "strip"):
        if cli.count != 4:
            raise BadArgs
        host = cli.arg(2)
        port = cli.arg_i(3)
        strip = command == "strip"
        if not port:
            raise ValueError("bad port")
        spin.iptag_set(tag, port, host=host, strip=strip)
    elif command == "reverse":
        if cli.count != 5:
            raise BadArgs
        port = cli.arg_i(2)
        dest_addr = cli.arg_x(3)
        dest_port = cli.arg_x(4)
        if not port:
            raise ValueError("bad port")
        spin.iptag_set(tag, port, reverse=True,
                       dest_addr=dest_addr, dest_port=dest_port)
    else:
        raise ValueError("bad command")


# ------------------------------------------------------------------------------

State = {
    "dead":  0, "pwrdn": 1, "rte":    2, "wdog":  3,
    "init":  4, "ready": 5, "c_main": 6, "run":   7,
    "sync0": 8, "sync1": 9, "pause": 10, "exit": 11,
    "idle": 15
}

Signal = {
    "init":  0,  "pwrdn": 1,  "stop":  2,  "start": 3,
    "sync0": 4,  "sync1": 5,  "pause": 6,  "cont": 7,
    "exit":  8,  "timer": 9,  "usr0":  10, "usr1": 11,
    "usr2":  12, "usr3":  13,
    "or":    16, "and":   17, "count": 18
}

# 0->MC, 1->P2P, 2->NN
Sig_type = {
    "init":  2,  "pwrdn": 2,  "stop":  2,  "start": 2,
    "sync0": 0,  "sync1": 0,  "pause": 0,  "cont": 0,
    "exit":  2,  "timer": 0,  "usr0":  0,  "usr1": 0,
    "usr2":  0,  "usr3":  0,
    "or":    1,  "and":   1,  "count": 1
}


def cmd_app_sig(cli):
    if cli.count < 3:
        raise BadArgs
    save_region = region = cli.arg(0)
    apps = cli.arg(1)
    signal = cli.arg(2)
    state = cli.arg(3) or 0

    app_id, app_mask = parse_apps(apps)
    region = parse_region(region, chip_x, chip_y)
    if signal not in Signal:
        raise ValueError("bad signal")
    _type = Sig_type[signal]
    signal = Signal[signal]
    if signal >= 16:  # and/or/count
        if cli.cout != 4:
            raise BadArgs
        if state not in State:
            raise ValueError("bad state")
        state = State[state]

    level = (region >> 16) & 3
    data = (app_mask << 8) | app_id
    mask = region & 0xFFFF

    if _type == 1:
        op, mode = 2, 2
        if signal >= 16:
            op, mode = 1, signal - 16
        data += (level << 26) + (op << 22) + (mode << 20)
        data += (state if op == 1 else signal) << 16
    else:
        data += signal << 16

    if debug:
        print("Type {} data {:08x} mask {:08x}".format(_type, data, mask))
        print("Region {:08x} signal {} state {}".format(region, signal, state))

    if _type == 1:
        xb = region >> 24
        yb = (region >> 16) & 0xFC
        # find a working chip in the target region (try at most 16 addresses)
        inc = 1 if level == 3 else 2  # if possible, spread out target chips
        for i in range(16):
            addr = (xb + (inc * (i >> 2)), yb + (inc * (i & 3)), 0)
            try:
                r, = spin.signal(_type, data, mask, addr=addr, unpack="<I")
            except SpinnTooManyRetriesException:
                raise
            except SpinnException:
                # General exception: just try somewhere else
                continue
            if signal == 18:
                print("Count {}".format(r))
            else:
                print("Mask 0x{:08x}".format(r))
            return
        print("Region {} is unreachable".format(save_region))
    else:
        spin.signal(_type, data, mask, addr=[])


def cmd_app_stop(cli):
    if cli.count != 1:
        raise BadArgs
    app_id, app_mask = parse_apps(cli.arg(0))

    SIG_STOP = Signal["stop"]
    arg1 = (NN_CMD.SIG0 << 4) | (0x3F << 16) | (0x00 << 8) | 0
    arg2 = (5 << 28) | (SIG_STOP << 16) | (app_mask << 8) | app_id
    arg3 = (1 << 31) | (0x3F << 8) | 0x00

    spin.nnp(arg1, arg2, arg3, addr=[])


# ------------------------------------------------------------------------------


def cmd_app_load_old(cli):
    if not 4 <= cli.count <= 5:
        raise BadArgs
    filename = cli.arg(0)
    mask = parse_cores(cli.arg(1))
    app_id = parse_app_id(cli.arg(2))
    flags = 0
    if cli.count == 4:
        if cli.arg(3) != "wait":
            raise ValueError("bad wait argument")
        flags = 1

    buf = read_file(filename, 65536)

    addr = 0x67800000
    spin.write(addr, buf)
    spin.ar(mask, app_id, flags)


def cmd_app_load(cli):
    if not 3 <= cli.count <= 4:
        raise BadArgs
    filename = cli.arg(0)
    region = parse_region(cli.arg(1), chip_x, chip_y)
    mask = parse_cores(cli.arg(2))
    app_id = cli.arg_i(3)
    flags = 0
    if cli.count == 5:
        if cli.arg(4) != "wait":
            raise ValueError("bad wait argument")
        flags = 1
    buf = read_file(filename, 65536)

    if debug:
        print("Region {:08x}, mask {:08x}".format(region, mask))

    spin.flood_fill(buf, region, mask, app_id, flags)


# ------------------------------------------------------------------------------


def cmd_data_load(cli):
    if cli.count != 3:
        raise BadArgs
    region = parse_region(cli.arg(1), chip_x, chip_y)
    addr = cli.arg_x(2)
    buf = read_file(cli.arg(0), 1024 * 1024)

    spin.flood_fill(buf, region, 0, 0, 0, base=addr, addr=[])


# ------------------------------------------------------------------------------


def global_write(addr, data, _type):
    if _type == 2 and addr & 3:
        raise ValueError("bad address alignment")
    if _type == 1 and addr & 1:
        raise ValueError("bad address alignment")

    if 0xF5007F00 <= addr < 0xF5008000:
        addr -= 0xf5007f00
        op = 0
    elif 0xF5000000 <= addr < 0xF5000100:
        addr -= 0xF5000000
        op = 1
    elif 0xF2000000 <= addr < 0xF2000100:
        addr -= 0xF2000000
        op = 2
    else:
        raise ValueError("bad address")

    key = ((NN_CMD.SIG1 << 24) | (0 << 20) | (_type << 18) | (op << 16) |
           (addr << 8) | 0)
    fr = (1 << 31) | (0x3F << 8) | 0xF8
    spin.nnp(key, data, fr, addr=[])


def cmd_gw(cli):
    if cli.count != 2:
        raise BadArgs
    global_write(cli.arg_x(0), cli.arg_x(1), 2)


def cmd_gh(cli):
    if cli.count != 2:
        raise BadArgs
    global_write(cli.arg_x(0), cli.arg_x(1), 1)


def cmd_gb(cli):
    if cli.count != 2:
        raise BadArgs
    global_write(cli.arg_x(0), cli.arg_x(1), 0)


# ------------------------------------------------------------------------------


def cmd_sload(cli):
    if cli.count != 2:
        raise BadArgs
    filename = cli.arg(0)
    addr = cli.arg_x(1)
    spin.write_file(addr, filename)


def cmd_sdump(cli):
    if cli.count != 3:
        raise BadArgs
    filename = cli.arg(0)
    addr = cli.arg_x(1)
    length = cli.arg_x(2)

    byte_count = 0
    with open(filename, "wb") as f:
        while byte_count != length:
            chunk_len = min(length - byte_count, 4096)
            data = spin.read(addr, chunk_len)
            addr += chunk_len
            if chunk_len != len(data):
                raise ValueError("length mismatch")
            f.write(data)
            byte_count += chunk_len


# ------------------------------------------------------------------------------


Cs = ("----", "PWRDN", "RTE", "WDOG", "INIT", "WAIT",  "SARK", "RUN", "SYNC0",
      "SYNC1", "PAUSE", "EXIT", "ST_12", "ST_13", "ST_14", "IDLE")
Rte = ("NONE", "RESET", "UNDEF", "SVC", "PABT", "DABT", "IRQ", "FIQ", "VIC",
       "ABORT", "MALLOC", "DIV0", "EVENT", "SWERR", "IOBUF", "ENABLE", "NULL",
       "PKT", "TIMER", "API", "VER")


def cpu_dump_header(fmt):
    if fmt == 0:
        print("Core State  Application       ID   Running  Started")
        print("---- -----  -----------       --   -------  -------")
    elif fmt == 1 or fmt == 2:
        print("Core State  Application       ID   "
              "     User0      User1      User2      User3")
        print("---- -----  -----------       --   "
              "     -----      -----      -----      -----")
    else:
        print("Core State  Application       ID   PCore  SWver")
        print("---- -----  -----------       --   -----  --------")


def cpu_dump(num, long, fmt):
    base = sv.read_var("sv.vcpu_base")
    sv.base("vcpu", base + sv.size("vcpu") * num)
    sv.read_struct("vcpu")

    timestamp = sv.get_var("vcpu.time")
    et = time.time() - timestamp
    if timestamp:
        _time = datetime.fromtimestamp(timestamp).strftime("%d %b %H:%M")
        et = "{:d}:{:02d}:{:02d}".format(et // 3600, (et // 60) % 60, et % 60)
    else:
        _time = " " * 12
        et = " " * 9

    if long:
        rt_code = sv.get_var("vcpu.rt_code")
        print(
            "Core {:2d}: app \"{}\", state {}, app_id {}, running {} "
            "({})".format(
                num, sv.get_var("vcpu.app_name"),
                Cs[sv.get_var("vcpu.cpu_state")],
                sv.get_var("vcpu.app_id"), et, _time))
        print("AP mbox:   cmd      {:02x}  msg     {:08x}".format(
            sv.get_var("vcpu.mbox_ap_cmd"), sv.get_var("vcpu.mbox_ap_msg")))
        print("MP mbox:   cmd      {:02x}  msg     {:08x}".format(
            sv.get_var("vcpu.mbox_mp_cmd"), sv.get_var("vcpu.mbox_mp_msg")))
        print("SW error:  line {:6d}  file    {:08x} count {}".format(
            sv.get_var("vcpu.sw_line"), sv.get_var("vcpu.sw_file"),
            sv.get_var("vcpu.sw_count")))
        print("RT error:  {:<6s}  PSR     {:08x} SP {:08x} LR {:08x}".format(
            Rte[rt_code], sv.get_var("vcpu.psr"),
            sv.get_var("vcpu.sp"), sv.get_var("vcpu.lr")))
        if rt_code:
            print(
                "r0-r7: {:08x} {:08x} {:08x} {:08x} {:08x} {:08x} {:08x} "
                "{:08x}".format(
                    sv.get_var("vcpu.r0"), sv.get_var("vcpu.r1"),
                    sv.get_var("vcpu.r2"), sv.get_var("vcpu.r3"),
                    sv.get_var("vcpu.r4"), sv.get_var("vcpu.r5"),
                    sv.get_var("vcpu.r6"), sv.get_var("vcpu.r7")))
    else:
        print("{:3d}  {:<6s} {:<16s} {:3d} ".format(
            num, Cs[sv.get_var("vcpu.cpu_state")],
            sv.get_var("vcpu.app_name"), sv.get_var("vcpu.app_id")), end="")
        if fmt == 1:
            print("    {:08x}   {:08x}   {:08x}   {:08x}".format(
                sv.get_var("vcpu.user0"), sv.get_var("vcpu.user1"),
                sv.get_var("vcpu.user2"), sv.get_var("vcpu.user3")))
        elif fmt == 2:
            print("  {:10u} {:10u} {:10u} {:10u}".format(
                sv.get_var("vcpu.user0"), sv.get_var("vcpu.user1"),
                sv.get_var("vcpu.user2"), sv.get_var("vcpu.user3")))
        elif fmt == 3:
            v = sv.get_var("vcpu.sw_ver")
            print("   {:2u}    {}.{}.{}".format(
                sv.get_var("vcpu.phys_cpu"),
                (v >> 16) & 255, (v >> 8) & 255, v & 255))
        else:
            swc = sv.get_var("vcpu.sw_count")
            print("{:9s}  {} {}".format(
                et, _time, (" SWC {}".format(swc) if swc else "")))


def cmd_ps(cli):
    if cli.count > 1:
        raise BadArgs

    if cli.count == 1 and re.match(r"^\d+$", cli.arg(0)):
        vc = cli.arg_i(0)
        if not 0 <= vc < 18:
            raise BadArgs
        cpu_dump(vc, 1, 0)
    elif cli.count == 1 and cli.arg(0) in ("x", "d", "p"):
        arg = cli.arg(0)
        fmt = 1 if arg == "x" else 2 if arg == "d" else 3
        cpu_dump_header(fmt)
        for vc in range(18):
            cpu_dump(vc, 0, fmt)
    else:
        cpu_dump_header(0)
        for vc in range(18):
            cpu_dump(vc, 0, 0)


# ------------------------------------------------------------------------------

SromInfo = namedtuple("SromInfo", ["PAGE", "ADDR"])
Srom_info = {
    "25aa1024": SromInfo(256, 24),
    "25aa080a": SromInfo(16, 16),
    "25aa160b": SromInfo(32, 16)}


def cmd_srom_type(cli):
    global srom_type
    if cli.count > 1:
        raise BadArgs
    elif cli.count == 1:
        _type = cli.arg(0)
        if _type not in Srom_info:
            raise ValueError("bad SROM type")
        srom_type = _type

    info = Srom_info[srom_type]
    print("SROM type {} (page {}, addr {})".format(
        srom_type, info.PAGE, info.ADDR))


def cmd_srom_read(cli):
    if cli.count > 1:
        raise BadArgs
    elif cli.count == 1:
        addr = cli.arg_x(0)
    else:
        addr = 0

    data = spin.srom_read(addr, 256, addr_size=Srom_info[srom_type].ADDR)
    hex_dump(data, addr=addr)


def cmd_srom_erase(cli):
    if cli.count:
        raise BadArgs
    spin.srom_erase()


def cmd_srom_write(cli):
    if cli.count != 2:
        raise BadArgs
    addr = cli.arg_x(1)
    buf = read_file(cli.arg(0), 128 * 1024)
    info = Srom_info[srom_type]

    print("Length {}, CRC32 0x{:08x}".format(len(buf), crc32(buf)))

    spin.srom_write(addr, buf, page_size=info.PAGE, addr_size=info.ADDR)


def cmd_srom_dump(cli):
    if cli.count != 3:
        raise BadArgs
    filename = cli.arg(0)
    addr = cli.arg_x(1)
    length = cli.arg_i(2)
    info = Srom_info[srom_type]

    byte_count = 0
    size = 256
    buf = b''
    while byte_count != length:
        _l = min(size, length - byte_count)
        data = spin.srom_read(addr, _l, addr_size=info.ADDR)
        if _l != len(data):
            raise ValueError("length mismatch")
        byte_count += _l
        addr += _l
        buf += data

    print("Length {}, CRC32 0x{:08x}".format(len(buf), crc32(buf)))

    with open(filename, "wb") as f:
        f.write(buf)


# ------------------------------------------------------------------------------


def check_ip(s):
    m = re.match(r"^/(\d+)$", s)
    if m:
        s = int(m.group(1))
        if not 8 <= s <= 32:
            raise ValueError("bad netmask shorthand")
        s = (0xFFFFFFFF << (32 - s)) & 0xFFFFFFFF
        s = ".".join((s >> x) & 0xFF for x in (24, 16, 8, 0))
    elif not re.match(r"^(?:\d+\.){3}\d+$", s):
        raise ValueError("bad IP address")

    v = s.split(".")
    if not all(0 <= n <= 255 for n in v):
        raise ValueError("bad IP address")
    v.reverse()
    return v


def get_srom_info(long):
    addr = 8
    length = 32

    # NB: this data is BIG ENDIAN
    d = spin.srom_read(addr, length, addr_size=Srom_info[srom_type].ADDR,
                       unpack=">8B 4B 4B 4B 2B H")

    flag = (d[2] << 8) + d[3]
    mac = "{:02x}:{:02x}:{:02x}:{:02x}:{:02x}:{:02x}".format(
        d[1], d[0], d[7], d[6], d[5], d[4])
    ip = ".".join(map(str, d[11:7:-1]))
    gw = ".".join(map(str, d[15:11:-1]))
    nm = ".".join(map(str, d[19:15:-1]))
    port = d[22]

    if long:
        print("Flag: {:04x}".format(flag))
        print("MAC:  {}".format(mac))
        print("IP:   {}".format(ip))
        print("GW:   {}".format(gw))
        print("NM:   {}".format(nm))
        print("Port: {:d}".format(port))
    else:
        print("{:04x} {} {} {} {} {:d}".format(
            flag, mac, ip, gw, nm, port))


def cmd_srom_init(cli):
    if cli.count == 0:
        get_srom_info(0)
        return
    elif cli.count != 6:
        raise BadArgs

    flag = cli.arg_x(0)
    mac = cli.arg(1)
    ip = check_ip(cli.arg(2))
    gw = check_ip(cli.arg(3))
    nm = check_ip(cli.arg(4))
    addresses = ip + gw + nm
    port = cli.arg_i(5)

    if not 0x8000 <= flag < 0x10000:
        raise ValueError("bad flag")
    if not re.match(r"(?i)^(?:[0-9a-f]{1,2}:){5}[0-9a-f]{1,2}$", mac):
        raise ValueError("bad mac")
    if not 1024 <= port < 65536:
        raise ValueError("bad port")

    mac = [int(m, base=16) for m in mac.split(":")]
    data = struct.pack(">2I 2B H 4B 4B 4B 4B 2B H 2I I",
                       0x553A0008, 0xF5007FE0, mac[4], mac[5], flag,
                       mac[0], mac[1], mac[2], mac[3],
                       *addresses, 0, 0, port, 0, 0, 0xAAAAAAAA)
    info = Srom_info[srom_type]
    spin.srom_write(0, data, page_size=info.PAGE, addr_size=info.ADDR)
    get_srom_info(1)


def cmd_srom_ip(cli):
    if cli.count == 0:
        get_srom_info(1)
        return
    if not 0 <= cli.count <= 3:
        raise BadArgs
    info = Srom_info[srom_type]

    addr = 16
    data = b''
    for a in range(cli.count):
        data += struct.pack(">4B", *check_ip(cli.arg(a)))
    length = len(data)

    print("Writing {} bytes at address {}".format(length, addr))

    spin.srom_write(addr, data, page=info.PAGE, addr=info.ADDR)

    print("Checking...")

    get_srom_info(1)
    rdata = spin.srom_read(addr, length, addr_size=info.ADDR)
    if len(rdata) != length or data != rdata:
        print("Oops! Try again?")
    else:
        print("Looks OK!")


# ------------------------------------------------------------------------------


def cmd_led(cli):
    Led = {"on": 3, "off": 2, "inv": 1, "flip": 1}

    if cli.count != 2:
        raise BadArgs
    num = cli.arg(0)  # This is a string!
    if not re.match(r"^[0-3]+$", num):
        raise BadArgs
    action = cli.arg(1).lower()
    if action not in Led:
        raise BadArgs

    c = sum(Led[action] << (int(led) * 2) for led in num)
    spin.led(c, addr=[0])


# ------------------------------------------------------------------------------


def cmd_remap(cli):
    if not 1 <= cli.count <= 2:
        raise BadArgs
    proc = cli.arg_i(0)
    if not 0 <= proc <= 17:
        raise BadArgs
    map_type = cli.arg(1).lower() if cli.count == 2 else "virt"
    if map_type not in ("phys", "virt"):
        raise BadArgs
    map_type = map_type == "phys"

    spin.scp_cmd(SCAMP_CMD.REMAP, arg1=proc, arg2=map_type)


# ------------------------------------------------------------------------------


def app_dump(data):
    print(" ID Cores Clean  Sema  Lead Mask")
    print("--- ----- -----  ----  ---- ----")

    for i in range(256):
        cores, clean, sema, lead, mask = struct.unpack_from(
            "<4BI", data, offset=i * 8)
        if cores or clean:
            print("{:3d} {:5d} {:5d} {:5d} {:5d} {:08x}".format(
                i, cores, clean, sema, lead, mask))


def cmd_app_dump(cli):
    if cli.count:
        raise BadArgs
    addr = sv.read_var("sv.app_data")
    app_dump(spin.read(addr, 256 * 8))


# ------------------------------------------------------------------------------


def rtr_heap(rtr_copy, rtr_free, name="Router"):
    print("\n{}\n{}".format(name, "-" * len(name)))

    p = 1  # RTR_ALLOC_FIRST
    while p:
        _next, free = spin.read(rtr_copy + 16 * p, 4, unpack="<HH")
        size = _next - p if _next else 0

        if free & 0x8000:
            fs = "AppID  {:3d}".format(free & 255)
        else:
            fs = "Free {:5d}".format(free)
        print("BLOCK {:5d}  Next {:5d}  {}  Size {}".format(
            p, _next, fs, size))
        p = _next

    p = rtr_free
    while p:
        _next, free = spin.read(rtr_copy + 16 * p, 4, unpack="<HH")
        size = _next - p if _next else 0

        print("FREE  {:5d}  Next {:5d}  Free {:5d}  Size {}".format(
            p, _next, free, size))
        p = free

    print("")


def rtr_dump(buf, fr):
    print("Entry  Route       (Core) (Link)  Key       Mask      AppID  Core")
    print("-----  765432109876543210 543210  ---       ----      -----  ----")
    print("")

    for i in range(1024):
        _next, free, route, key, mask = struct.unpack_from(
            "<2H3I", buf, offset=16 * i)
        if route >= 0xFF000000:
            continue
        print("{:4d}:  {:018b} {:06b}  {:08x}  {:08x}  {:5d}  {:4d}".format(
            i, (route >> 6) & 0x3FFFF, route & 0x3F, key, mask, free & 0xFF,
            (free >> 8) & 0x1F))

    print("  FR:  {:018b} {:06b}".format((fr >> 6) & 0x3FFFF, fr & 0x3F))


def cmd_rtr_init(cli):
    if cli.count:
        raise BadArgs
    spin.scp_cmd(SCAMP_CMD.RTR)


def cmd_rtr_dump(cli):
    if cli.count:
        raise BadArgs

    rtr = sv.read_var("sv.rtr_copy")
    fr = sv.read_var("sv.fr_copy")
    rtr_dump(spin.read(rtr, 1025 * 16), fr)


def rtr_wait(v):
    m = v & 0x0F         # mantissa
    e = (v >> 4) & 0x0F  # exponent
    return (m + (0x10 if e > 4 else (0xF0 >> e) & 0x0F)) << e


def cmd_rtr_diag(cli):
    if cli.count >= 2:
        raise BadArgs
    arg0 = cli.arg(0).lower() if cli.count else ""

    rtrc = ("Loc  MC:", "Ext  MC:", "Loc  PP:", "Ext  PP:",
            "Loc  NN:", "Ext  NN:", "Loc  FR:", "Ext  FR:",
            "Dump MC:", "Dump PP:", "Dump NN:", "Dump FR:",
            "Cntr 12:", "Cntr 13:", "Cntr 14:", "Cntr 15:")

    rcr, = spin.read(0xE1000000, 4, type="word", unpack="<I")
    print("\nCtrl Reg:  0x{:08x} (Mon {}, Wait1 {}, Wait2 {})".format(
        rcr, (rcr >> 8) & 0x1F, rtr_wait(rcr >> 16), rtr_wait(rcr >> 24)))

    es, = spin.read(0xE1000014, 4, type="word", unpack="<I")
    print("Err Stat:  0x{:08x}\n".format(es))

    data = spin.read(0xE1000300, 64, type="word", unpack="<16I")
    for label, datum in zip(rtrc, data):
        print("{:<10s} {}".format(label, datum))

    if arg0 == "clr":
        c = struct.pack("<I", 0xFFFFFFFF)
        spin.write(0xF100002C, c, type="word")


def cmd_rtr_heap(cli):
    if cli.count:
        raise BadArgs

    rtr_copy = sv.read_var("sv.rtr_copy")
    rtr_free = sv.read_var("sv.rtr_free")
    rtr_heap(rtr_copy, rtr_free)


# ------------------------------------------------------------------------------


def cmd_reset(cli):
    if cli.count:
        raise BadArgs
    if bmp is None:
        raise RuntimeError("BMP not set")

    bmp.reset(bmp_range)


def cmd_power(cli):
    if cli.count != 1:
        raise BadArgs
    power = cli.arg(0).lower()
    if power not in ("off", "on"):
        raise BadArgs
    power = power == "on"
    if bmp is None:
        raise RuntimeError("BMP not set")

    bmp.power(power, bmp_range, timeout=3.0 if power else bmp.timeout)


def cmd_p2p_route(cli):
    if cli.count > 1:
        raise BadArgs
    elif not cli.count:
        print("Flags 0x{:02x}".format(spin.flags))
        return

    enable = cli.arg(0).lower()
    if enable not in ("off", "on"):
        raise BadArgs

    flags = spin.flags()
    spin.flags(flags & ~0x20 if enable == "on" else flags | 0x20)


# ------------------------------------------------------------------------------


def cmd_debug(cli):
    global debug
    if cli.count > 1:
        raise BadArgs
    elif cli.count:
        debug = cli.arg_i(0)

    spin.debug(debug)
    if bmp is not None:
        bmp.debug(debug)

    print("Debug {}".format(debug))


def cmd_sleep(cli):
    naptime = 1.0
    if cli.count > 1:
        raise BadArgs
    elif cli.count:
        naptime = float(cli.arg(0))

    time.sleep(naptime)


def cmd_timeout(cli):
    if cli.count > 1:
        raise BadArgs
    elif cli.count:
        t = float(cli.arg(0))
        spin.timeout(t)

    print("Timeout {}".format(spin.timeout()))


def cmd_cmd(cli):
    if not 1 <= cli.count <= 4:
        raise BadArgs
    op = cli.arg_i(0)
    arg1 = cli.arg_x(1) if cli.count >= 2 else 0
    arg2 = cli.arg_x(2) if cli.count >= 3 else 0
    arg3 = cli.arg_x(3) if cli.count == 4 else 0

    spin.scp_cmd(op, arg1=arg1, arg2=arg2, arg3=arg3)


def cmd_version(cli):
    if cli and cli.count:
        raise BadArgs
    print("# pybug - version {}".format(fec_version))


# ------------------------------------------------------------------------------


def cmd_expert(cli):
    if cli.count:
        raise BadArgs
    global expert

    if expert:
        return
    expert = True
    _cli.cmd(expert_cmds, 0)

    print("# You are now an expert!")


# ------------------------------------------------------------------------------


spin_cmds = {
    "version": (
        cmd_version,
        "",
        "Show ybug version"),
    "expert": (
        cmd_expert,
        "",
        "Enable expert commands"),
    "debug": (
        cmd_debug,
        "<num.D>",
        "Set debug level"),
    "timeout": (
        cmd_timeout,
        "<secs.R>",
        "Set target timeout"),
    "sleep": (
        cmd_sleep,
        "<secs.D>",
        "Sleep (secs)"),
    "sp": (
        cmd_sp,
        "<chip_x.D> <chip_y.D> <core.D>",
        "Select SpiNNaker chip and core"),
    "sver": (
        cmd_sver,
        "",
        "Show SpiNNaker S/W version"),
    "ps": (
        cmd_ps,
        "[<core.D>|d|x|p]",
        "Display core state"),
    "smemb": (
        cmd_smemb,
        "<addr.X>",
        "Read SpiNNaker memory (bytes)"),
    "smemh": (
        cmd_smemh,
        "<addr.X>",
        "Read SpiNNaker memory (half-words)"),
    "smemw": (
        cmd_smemw,
        "<addr.X>",
        "Read SpiNNaker memory (words)"),
    "sload": (
        cmd_sload,
        "<file.F> <addr.X>",
        "Load SpiNNaker memory from file"),
    "sw": (
        cmd_sw,
        "<addr.X> [<data.X>]",
        "Read/write Spinnaker word"),
    "sh": (
        cmd_sh,
        "<addr.X> [<data.X>]",
        "Read/write Spinnaker half-word"),
    "sb": (
        cmd_sb,
        "<addr.X> [<data.X>]",
        "Read/write Spinnaker byte"),
    "sfill": (
        cmd_sfill,
        "<from_addr.X> <to_addr.X> <word.X>",
        "Fill Spinnaker memory (words)"),
    "boot": (
        cmd_boot,
        "[<boot_file.F>] [<conf_file.F>]",
        "System bootstrap"),
    "app_load": (
        cmd_app_load,
        "<file.F> .|@<X.D>,<Y.D>|<region> <cores> <app_id.D> [wait]",
        "Load application"),
    "app_stop": (
        cmd_app_stop,
        "<app_id.D>[-<app_id.D>]",
        "Stop application(s)"),
    "app_sig": (
        cmd_app_sig,
        "<region> <app_id.D>[-<app_id.D>] <signal> [state]",
        "Send signal to application"),
    "data_load": (
        cmd_data_load,
        "<file.F> <region> <addr.X>",
        "Load data to all chips in region"),
    "rtr_load": (
        cmd_rtr_load,
        "<file.F> <app_id.D>",
        "Load router file"),
    "rtr_dump": (
        cmd_rtr_dump,
        "",
        "Dump router MC table"),
    # "rtr_init": (
    #     cmd_rtr_init,
    #     "",
    #     "Initialise router MC table and heap"),
    "rtr_heap": (
        cmd_rtr_heap,
        "",
        "Dump router MC heap"),
    "rtr_diag": (
        cmd_rtr_diag,
        "[clr]",
        "Show router diagnostic counts, etc"),
    "iobuf": (
        cmd_iobuf,
        "<core.D> [<file.F>]",
        "Display/write I/O buffer for core"),
    "sdump": (
        cmd_sdump,
        "<file.F> <addr.X> <len.X>",
        "Dump SpiNNaker memory to file"),
    "iptag": (
        cmd_iptag,
        """<tag.D> <cmd.S> args...
               <tag.D> clear
               <tag.D> set     <host.P> <port.D>
               <tag.D> strip   <host.P> <port.D>
               <tag.D> reverse <port.D> <address.X> <port.X>""",
        "Set up IPTags"),
    "led": (
        cmd_led,
        "<0123>* on|off|inv|flip",
        "Set/clear LEDs"),
    "heap": (
        cmd_heap,
        "sdram|sysram|system",
        "Dump heaps"),
    "reset": (
        cmd_reset,
        "",
        "Reset Spinnakers via BMP"),
    "power": (
        cmd_power,
        "on|off",
        "Switch power on/off via BMP"),
}

expert_cmds = {
    "gw": (
        cmd_gw,
        "<addr.X> <data.X>",
        "Global word write"),
    "gh": (
        cmd_gh,
        "<addr.X> <data.X>",
        "Global half-word write"),
    "gb": (
        cmd_gb,
        "<addr.X> <data.X>",
        "Global byte write"),
    "lmemw": (
        cmd_lmemw,
        "<link.D> <addr.X>",
        "Read SpiNNaker memory via link (words)"),
    "lw": (
        cmd_lw,
        "<link.D> <addr.X> [<data.X]",
        "Read/write SpiNNaker word via link"),
    "srom_ip": (
        cmd_srom_ip,
        "[<ip_addr.P> [<gw_addr.P> [<net_mask.P>]]]",
        "Set IP address in serial ROM"),
    "srom_read": (
        cmd_srom_read,
        "<addr.X>",
        "Read serial ROM data"),
    "srom_type": (
        cmd_srom_type,
        "25aa1024|25aa080a|25aa160b",
        "Set SROM type"),
    "srom_dump": (
        cmd_srom_dump,
        "<file.F> <addr.X> <len.D>",
        "Dump serial ROM data"),
    "srom_write": (
        cmd_srom_write,
        "<file.F> <addr.X>",
        "Write serial ROM data"),
    "srom_erase": (
        cmd_srom_erase,
        "",
        "Erase (all) serial ROM data"),
    "srom_init": (
        cmd_srom_init,
        "<Flag.X> <MAC.M> <ip_addr.P> <gw_addr.P> <net_mask.P> <port.D>",
        "Initialise serial ROM"),
    "remap": (
        cmd_remap,
        "<core.D> [phys|virt]",
        "Remove bad core from core map"),
    "p2p_route": (
        cmd_p2p_route,
        "[on|off]",
        "Control P2P routing"),
    "app_dump": (
        cmd_app_dump,
        "",
        "Show app data for this chip"),
    "cmd": (
        cmd_cmd,
        '<cmd.D> <arg1.X> <arg2.X> <arg3.X>',
        'User specified command'),
}

# ------------------------------------------------------------------------------


def usage():
    print("usage: pybug <options> <hostname>", file=sys.stderr)
    print("  -bmp  <name>[/<slots>]   - set BMP target", file=sys.stderr)
    print("  -version                 - print version number", file=sys.stderr)
    print("  -norl                    - don't use 'ReadLine'", file=sys.stderr)
    print("  -expert                  - set 'expert' mode", file=sys.stderr)
    print("  -debug <value>           - set debug variable", file=sys.stderr)
    sys.exit(1)


def process_args():
    global spinn_target, bmp_target, expert, _readline, debug
    global bmp_range
    _range = "0"
    args = list(sys.argv)
    while args:
        arg = args.pop(0)
        if arg == "-bmp":
            bmp_target = args.pop(0)
            m = re.match(r"^(.*)/(\S+)$", bmp_target)
            if m:
                bmp_target, _range = m.groups()
        elif arg == "-version":
            cmd_version(None)
            sys.exit()
        elif arg == "-debug":
            debug = int(args.pop(0))
        elif arg == "-norl":
            _readline = False
        elif arg == "-expert":
            expert = True
        elif not re.match(r"^-", arg):
            spinn_target = arg
            break
        else:
            usage()
    if args:
        usage()

    bmp_range = parse_bits(_range, 0, 23)
    if spinn_target is None:
        print("target not specified", file=sys.stderr)
        sys.exit(1)
    prompt = spinn_target
    if not re.match(r"^\d", prompt):
        prompt = re.sub(r"\..+", "", prompt)
    prompt += ":0,0,0 > "
    return prompt


def open_targets():
    global spin, sv, bmp
    spin = SCAMPCmd(target=spinn_target, port=spin_port, debug=debug)
    sv = Struct(scp=spin)
    if bmp_target is not None:
        bmp = BMPCmd(target=bmp_target, port=bmp_port, debug=debug)


class Completer(object):
    def __init__(self, rl):
        self._rl = rl
        self._stored = [None]

    def __call__(self, text, state):
        if self._rl.get_begidx():
            # No filename completion; that's complicated!
            return None
        if not state:
            # Add None to the end to mark end of matches
            # https://eli.thegreenplace.net/2016/basics-of-using-the-readline-library/
            self._stored = list(_cli.commands_starting_with(text)) + [None]
        word = self._stored[state]
        if word and len(self._stored) == 1:
            word += " "
        return word


def init_readline():
    if not _readline:
        return None

    import readline
    readline.set_completer(Completer(readline))
    return readline


def main():
    global _cli
    prompt = process_args()
    rl = init_readline()

    open_targets()
    cmd_version(None)

    _cli = CLI(sys.stdin, prompt, spin_cmds, rl)
    if expert:
        _cli.cmd(expert_cmds, 0)
    _cli.run()
