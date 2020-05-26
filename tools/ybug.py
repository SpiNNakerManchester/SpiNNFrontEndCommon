import re
import struct
import time
import tools.cli
import tools.boot
import tools.struct
import tools.cmd
from tools.util import (
    read_file, hex_dump, parse_cores, parse_region, parse_apps, parse_bits,
    sllt_version)
import sys

# ------------------------------------------------------------------------------

spin = None          # SpiNN::Cmd object for SpiNNaker
bmp = None           # SpiNN::Cmd object for BMP (or undef)
cli = None           # SpiNN::CLI object

sv = None            # SpiNN::Struct object

debug = False        # Enable verbosity
expert = False       # Expert mode
readline = True      # Use readline

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

CMD_REMAP = 16
CMD_ALLOC = 28
CMD_RTR   = 29
CMD_RESET = 55
CMD_POWER = 57

NN_CMD_SIG0 = 0
NN_CMD_SIG1 = 4

# ------------------------------------------------------------------------------


class BadArgs(Exception):
    def __str__(self):
        return "bad args"


def cmd_boot(cmd):
    if cmd.count > 2:
        raise BadArgs
    file = cmd.arg(0) or "scamp.boot"
    conf = cmd.arg(1) or ""

    try:
        # Warn if already booted
        try:
            spin.ver(addr=[], timeout=0.1)
            print("Warning: Already booted")
        except:  # pylint: disable=bare-except
            pass

        tools.boot.boot(spinn_target, file, conf, debug=debug)

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


def cmd_sver(cmd):
    if cmd.count:
        raise BadArgs
    print(spin.ver())


def cmd_lw(cmd):
    if not 2 <= cmd.count <= 3:
        raise BadArgs
    link = int(cmd.arg(0), base=0)
    addr = int(cmd.arg(1), base=0)

    if cmd.count == 2:
        data = struct.unpack("<I", spin.link_read(link, addr, 4))
        print("{:08x} = {:08x}".format(addr, data[0]))
    else:
        data = struct.pack("<I", int(cmd.arg(2), base=0))
        spin.link_write(link, addr, data)


def cmd_lmemw(cmd):
    if cmd.count != 2:
        raise BadArgs
    link = int(cmd.arg(0), base=0)
    addr = int(cmd.arg(1), base=0)
    data = spin.link_read(link, addr, 256)
    hex_dump(data, addr=addr, format="word")


def cmd_smemw(cmd):
    if cmd.count > 1:
        raise BadArgs
    addr = int(cmd.arg(0), base=0) if cmd.count else 0
    data = spin.read(addr, 256, type="word")
    hex_dump(data, addr=addr, format="word")


def cmd_smemh(cmd):
    if cmd.count > 1:
        raise BadArgs
    addr = int(cmd.arg(0), base=0) if cmd.count else 0
    data = spin.read(addr, 256, type="half")
    hex_dump(data, addr=addr, format="half", width=16)


def cmd_smemb(cmd):
    if cmd.count > 1:
        raise BadArgs
    addr = int(cmd.arg(0), base=0) if cmd.count else 0
    data = spin.read(addr, 256, type="byte")
    hex_dump(data, addr=addr)


def cmd_sw(cmd):
    if not 1 <= cmd.count <= 2:
        raise BadArgs
    addr = int(cmd.arg(0), base=0)
    if cmd.count == 1:
        data = struct.unpack("<I", spin.read(addr, 4, type="word"))
        print("{:08x} = {:08x}".format(addr, data[0]))
    else:
        data = struct.pack("<I", int(cmd.arg(1), base=0))
        spin.write(addr, data, type="word")


def cmd_sh(cmd):
    if not 1 <= cmd.count <= 2:
        raise BadArgs
    addr = int(cmd.arg(0), base=0)
    if cmd.count == 1:
        data = struct.unpack("<H", spin.read(addr, 2, type="half"))
        print("{:08x} = {:04x}".format(addr, data[0]))
    else:
        data = struct.pack("<H", int(cmd.arg(1), base=0))
        spin.write(addr, data, type="half")


def cmd_sb(cmd):
    if not 1 <= cmd.count <= 2:
        raise BadArgs
    addr = int(cmd.arg(0), base=0)
    if cmd.count == 1:
        data = struct.unpack("<B", spin.read(addr, 1, type="byte"))
        print("{:08x} = {:02x}".format(addr, data[0]))
    else:
        data = struct.pack("<B", int(cmd.arg_x(1), base=0))
        spin.write(addr, data, type="byte")


def cmd_sfill(cmd):
    if cmd.count != 3:
        raise BadArgs
    _from = int(cmd.arg(0), base=0)
    to = int(cmd.arg(1), base=0)
    fill = int(cmd.arg(2), base=0)
    spin.fill(_from, fill, to-_from)


def cmd_sp(cmd):
    global chip_x, chip_y, cpu
    if not cmd.count or (cmd.count == 1 and cmd.arg(0) == "root"):
        # Try and determine the true coordinates of the root chip
        root_x, root_y = 0, 0
        try:
            version_info = spin.ver(addr=[], raw=1, timeout=0.1)
            root_x = version_info[3]
            root_y = version_info[2]
        except:  # pylint: disable=bare-except
            pass
        chip_x, chip_y, cpu = spin.addr(root_x, root_y)
    elif cmd.count == 1:
        chip_x, chip_y, cpu = spin.addr(int(cmd.arg(0), base=0))
    elif cmd.count == 2:
        chip_x, chip_y, cpu = spin.addr(
            int(cmd.arg(0), base=0), int(cmd.arg(1), base=0))
    elif cmd.count == 3:
        chip_x, chip_y, cpu = spin.addr(
            int(cmd.arg(0), base=0), int(cmd.arg(1), base=0),
            int(cmd.arg(2), base=0))
    else:
        raise BadArgs

    # Update the prompt
    cmd.prompt = re.sub(
        r":.+", ":{},{},{} > ".format(chip_x, chip_y, cpu), cmd.prompt)


# ------------------------------------------------------------------------------


def _iodump(fh, buf):
    _next, _time, _ms, _len = struct.unpack_from("<IIII", buf)
    base = 16
    _string = buf[base:base + _len]
    fh.write(_string)
    return _next


def cmd_iobuf(cmd):
    if not 1 <= cmd.count <= 2:
        raise BadArgs
    core = int(cmd.arg(0), base=0)

    opened = cmd.count > 1
    if opened:
        fh = open(cmd.arg(1))
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
    heap_free, heap_first, _, free_bytes = struct.unpack(
        "<IIII", spin.read(heap, 16))
    print("")
    print("{} {}".format(name, free_bytes))
    print("-" * len(name))

    p = heap_first
    while p:
        _next, free = struct.unpack("<II", spin.read(p, 8))
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
        _next, free = struct.unpack("<II", spin.read(p, 8))
        size = 0 if _next == 0 else _next - p - 8
        print("FREE   {:8x}  Next {:8x}  Free  {:08x}  Size {}".format(
            p, _next, free, size))
        p = free


def cmd_heap(cmd):
    if cmd.count > 1:
        raise BadArgs
    arg = cmd.arg(0) if cmd.count else None

    if arg is None or arg == "sdram":
        dump_heap(sv.read_var("sv.sdram_heap"), "SDRAM")
    if arg is None or arg == "sysram":
        dump_heap(sv.read_var("sv.sysram_heap"), "SysRAM")
    if arg is None or arg == "system":
        dump_heap(sv.read_var("sv.sys_heap"), "System")

    print("")


# ------------------------------------------------------------------------------


def cmd_rtr_load(cmd):
    if cmd.count != 2:
        raise BadArgs
    _file = cmd.arg(0)
    app_id = int(cmd.arg(1), base=0)
    if not APP_MIN <= app_id <= APP_MAX:
        raise ValueError("Bad App ID")

    buf = read_file(_file, 65536)
    size = len(buf)
    if size % 16 or not 32 <= size <= 1024 * 16:
        raise ValueError("Funny file size: {}".format(size))
    size = (size - 16) % 16

    addr = 0x67800000
    spin.write(addr, buf)
    base = struct.unpack("<I", spin.scp_cmd(
        CMD_ALLOC, arg1=(app_id << 8) + 3, arg2=size))
    if not base:
        raise RuntimeError("no room in router heap")
    spin.scp_cmd(
        CMD_RTR, arg1=(size << 16) + (app_id << 8 + 2), arg2=addr, arg3=base)


# ------------------------------------------------------------------------------


def ipflag(flags):
    r =  "T" if flags & 0x4000 else ""
    r += "A" if flags & 0x2000 else ""
    r += "R" if flags & 0x0200 else ""
    r += "S" if flags & 0x0100 else ""
    return r


def dump_iptag():
    tto, pool, fix = struct.unpack("<BxBB", spin.iptag_tto(255))
    _max = pool + fix
    tto = (1 << (tto - 1)) / 100 if tto else 0

    print("IPTags={} (F={}, T={}), TTO={}s\n".format(_max, fix, pool, tto))
    print("Tag    IP address    TxPort RxPort  T/O   Flags    Addr    Port      Count")
    print("---    ----------    ------ ------  ---   -----    ----    ----      -----")

    for i in range(_max):
        (ip, _mac, tx_port, timeout, flags, count, rx_port, spin_addr,
         spin_port_id) = struct.unpack("<4s6sHHHIHHB", spin.iptag_get(i, 1))
        if flags & 0x8000:  # Tag in use
            print("{:3d}  {:-15s}  {:5d}  {:5d}  {:-4s}  {:-4s}   0x{:04x}    "
                  "0x{:02x} {:10d}".format(
                i, ".".join(map(str, struct.unpack("BBBB", ip))),
                tx_port, rx_port, timeout / 100, ipflag(flags), spin_addr,
                spin_port_id, count))


def cmd_iptag(cmd):
    if not cmd.count:
        dump_iptag()
        return
    if cmd.count < 2:
        raise BadArgs

    tag = int(cmd.arg(0), base=0)
    if not MIN_TAG <= tag <= MAX_TAG:
        raise ValueError("bad tag")
    command = cmd.arg(1)

    if command == "clear":
        if cmd.count != 2:
            raise BadArgs
        spin.iptag_clear(tag)
    elif command in ("set", "strip"):
        if cmd.count != 4:
            raise BadArgs
        host = cmd.arg(2)
        port = int(cmd.arg(3), base=0)
        strip = command == "strip"
        if not port:
            raise ValueError("bad port")
        spin.iptag_set(tag, port, host=host, strip=strip)
    elif command == "reverse":
        if cmd.count != 5:
            raise BadArgs
        port = int(cmd.arg(2), base=0)
        dest_addr = int(cmd.arg(3), base=16)
        dest_port = int(cmd.arg(4), base=16)
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


def cmd_app_size(cmd):
    if cmd.count < 3:
        raise BadArgs
    save_region = region = cmd.arg(0)
    apps = cmd.arg(1)
    signal = cmd.arg(2)
    state = cmd.arg(3) or 0

    app_id, app_mask = parse_apps(apps)
    if not 0 <= app_id <= 255:
        raise ValueError("bad app_id")
    region = parse_region(region)
    if not region:
        raise ValueError("bad region")
    if signal not in Signal:
        raise ValueError("bad signal")
    type = Sig_type[signal]
    signal = Signal[signal]
    if signal >= 16:  # and/or/count
        if cmd.cout != 4:
            raise BadArgs
        if state not in State:
            raise ValueError("bad state")
        state = State[state]

    level = (region >> 16) & 3
    data = (app_mask << 8) | app_id
    mask = region & 0xFFFF

    if type == 1:
        op, mode = 2, 2
        if signal >= 16:
            op, mode = 1, signal - 16
        data += (level << 26) + (op << 22) + (mode << 20)
        data += (state if op == 1 else signal) << 16
    else:
        data += signal << 16

    if debug:
        print("Type {} data {:08x} mask {:08x}".format(type, data, mask))
        print("Region {:08x} signal {} state {}".format(region, signal, state))

    if type == 1:
        xb = region >> 24
        yb = (region >> 16) & 0xFC
        # find a working chip in the target region (try at most 16 addresses)
        inc = 1 if level == 3 else 2  # if possible, spread out target chips
        for i in range(16):
            addr = (xb + (inc * (i >> 2)), yb + (inc * (i & 3)), 0)
            try:
                r = struct.unpack("<I", spin.signal(
                    type, data, mask, addr=addr))
            except SpinnRetries:  # FIXME
                raise
            except:  # pylint: disable=bare-except
                # General exception: just try somewhere else
                continue
            if signal == 18:
                print("Count {}".format(r))
            else:
                print("Mask 0x{:08x}".format(r))
            return
        print("Region {} is unreachable".format(save_region))
    else:
        spin.signal(type, data, mask, addr=[])


def cmd_app_stop(cmd):
    if cmd.count != 1:
        raise BadArgs
    app_id, app_mask = parse_apps(cmd.arg(0))
    if not 0 <= app_id <= 255:
        raise ValueError("bad app_id")

    SIG_STOP = Signal["stop"]
    arg1 = (NN_CMD_SIG0 << 4) | (0x3F << 16) | (0x00 << 8) | 0
    arg2 = (5 << 28) | (SIG_STOP << 16) | (app_mask << 8) | app_id
    arg3 = (1 << 31) | (0x3F << 8) | 0x00

    spin.nnp(arg1, arg2, arg3, addr=[])

# ------------------------------------------------------------------------------


def cmd_expert(cmd):
    if cmd.count:
        raise BadArgs
    global expert

    if expert:
        return
    expert = True
    cli.cmd(expert_cmds, 0)

    print("# You are now an expert!")


# ------------------------------------------------------------------------------


spin_cmds = {
    "version": (cmd_version,
        "",
        "Show ybug version"),
    "expert": (cmd_expert,
        "",
        "Enable expert commands"),
    "debug": (cmd_debug,
        "<num.D>",
        "Set debug level"),
    "timeout": (cmd_timeout,
        "<secs.R>",
        "Set target timeout"),
    "sleep": (cmd_sleep,
        "<secs.D>",
        "Sleep (secs)"),
    "sp": (cmd_sp,
        "<chip_x.D> <chip_y.D> <core.D>",
        "Select SpiNNaker chip and core"),
    "sver": (cmd_sver,
        "",
        "Show SpiNNaker S/W version"),
    "ps": (cmd_ps,
        "[<core.D>|d|x|p]",
        "Display core state"),
    "smemb": (cmd_smemb,
        "<addr.X>",
        "Read SpiNNaker memory (bytes)"),
    "smemh": (cmd_smemh,
        "<addr.X>",
        "Read SpiNNaker memory (half-words)"),
    "smemw": (cmd_smemw,
        "<addr.X>",
        "Read SpiNNaker memory (words)"),
    "sload": (cmd_sload,
        "<file.F> <addr.X>",
        "Load SpiNNaker memory from file"),
    "sw": (cmd_sw,
        "<addr.X> [<data.X>]",
        "Read/write Spinnaker word"),
    "sh": (cmd_sh,
        "<addr.X> [<data.X>]",
        "Read/write Spinnaker half-word"),
    "sb": (cmd_sb,
        "<addr.X> [<data.X>]",
        "Read/write Spinnaker byte"),
    "sfill": (cmd_sfill,
        "<from_addr.X> <to_addr.X> <word.X>",
        "Fill Spinnaker memory (words)"),
    "boot": (cmd_boot,
        "[<boot_file.F>] [<conf_file.F>]",
        "System bootstrap"),
    "app_load": (cmd_app_load,
        "<file.F> .|@<X.D>,<Y.D>|<region> <cores> <app_id.D> [wait]",
        "Load application"),
    "app_stop": (cmd_app_stop,
        "<app_id.D>[-<app_id.D>]",
        "Stop application(s)"),
    "app_sig": (cmd_app_sig,
        "<region> <app_id.D>[-<app_id.D>] <signal> [state]",
        "Send signal to application"),
    "data_load": (cmd_data_load,
        "<file.F> <region> <addr.X>",
        "Load data to all chips in region"),
    "rtr_load": (cmd_rtr_load,
        "<file.F> <app_id.D>",
        "Load router file"),
    "rtr_dump": (cmd_rtr_dump,
        "",
        "Dump router MC table"),
#    "rtr_init": (cmd_rtr_init,
#         "",
#         "Initialise router MC table and heap"),
    "rtr_heap": (cmd_rtr_heap,
        "",
        "Dump router MC heap"),
    "rtr_diag": (cmd_rtr_diag,
        "[clr]",
        "Show router diagnostic counts, etc"),
    "iobuf": (cmd_iobuf,
        "<core.D> [<file.F>]",
        "Display/write I/O buffer for core"),
    "sdump": (cmd_sdump,
        "<file.F> <addr.X> <len.X>",
        "Dump SpiNNaker memory to file"),
    "iptag": (cmd_iptag,
        """<tag.D> <cmd.S> args...
               <tag.D> clear
               <tag.D> set     <host.P> <port.D>
               <tag.D> strip   <host.P> <port.D>
               <tag.D> reverse <port.D> <address.X> <port.X>""",
        "Set up IPTags"),
    "led": (cmd_led,
        "<0123>* on|off|inv|flip",
        "Set/clear LEDs"),
    "heap": (cmd_heap,
        "sdram|sysram|system",
        "Dump heaps"),
    "reset": (cmd_reset,
        "",
        "Reset Spinnakers via BMP"),
    "power": (cmd_power,
        "on|off",
        "Switch power on/off via BMP"),
    "pause": (tools.cli.Pause,
        "<text.S>",
        "Print string and wait for Enter key"),
    "echo": (tools.cli.Echo,
        "<text.S>",
        "Print string"),
    "quit": (tools.cli.Quit,
        "",
        "Quit"),
    "help": (tools.cli.Help,
        "",
        "Provide help"),
    "@": (tools.cli.At,
        "<file.F> [quiet]",
        "Read commands from file"),
    "?": (tools.cli.Query,
        "",
        "List commands"),
}

expert_cmds = {
    "gw": (cmd_gw,
        "<addr.X> <data.X>",
        "Global word write"),
    "gh": (cmd_gh,
        "<addr.X> <data.X>",
        "Global half-word write"),
    "gb": (cmd_gb,
        "<addr.X> <data.X>",
        "Global byte write"),
    "lmemw": (cmd_lmemw,
        "<link.D> <addr.X>",
        "Read SpiNNaker memory via link (words)"),
    "lw": (cmd_lw,
        "<link.D> <addr.X> [<data.X]",
        "Read/write SpiNNaker word via link"),
    "srom_ip": (cmd_srom_ip,
        "[<ip_addr.P> [<gw_addr.P> [<net_mask.P>]]]",
        "Set IP address in serial ROM"),
    "srom_read": (cmd_srom_read,
        "<addr.X>",
        "Read serial ROM data"),
    "srom_type": (cmd_srom_type,
        "25aa1024|25aa080a|25aa160b",
        "Set SROM type"),
    "srom_dump": (cmd_srom_dump,
        "<file.F> <addr.X> <len.D>",
        "Dump serial ROM data"),
    "srom_write": (cmd_srom_write,
        "<file.F> <addr.X>",
        "Write serial ROM data"),
    "srom_erase": (cmd_srom_erase,
        "",
        "Erase (all) serial ROM data"),
    "srom_init": (cmd_srom_init,
        "<Flag.X> <MAC.M> <ip_addr.P> <gw_addr.P> <net_mask.P> <port.D>",
        "Initialise serial ROM"),
    "remap": (cmd_remap,
        "<core.D> [phys|virt]",
        "Remove bad core from core map"),
    "p2p_route": (cmd_p2p_route,
        "[on|off]",
        "Control P2P routing"),
    "app_dump": (cmd_app_dump,
        "",
        "Show app data for this chip"),
    "cmd": (cmd_cmd,
        '<cmd.D> <arg1.X> <arg2.X> <arg3.X>',
        'User specified command'),
}
