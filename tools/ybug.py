import re
import struct
import time
import tools.cli
import tools.boot
import tools.struct
import tools.cmd
from tools.util import hex_dump

#-------------------------------------------------------------------------------

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

(chip_x, chip_y, chip_p) = (0, 0, 0)

srom_type = "25aa1024"  # SROM type

#-------------------------------------------------------------------------------

CMD_REMAP = 16
CMD_ALLOC = 28
CMD_RTR   = 29
CMD_RESET = 55
CMD_POWER = 57

NN_CMD_SIG0 = 0
NN_CMD_SIG1 = 4

#-------------------------------------------------------------------------------


class BadArgs(Exception):
    def __str__(self):
        return "bad args"


def cmd_boot(cmd):
    file = cmd.arg(0) or "scamp.boot"
    conf = cmd.arg(1) or ""
    if cmd.count > 2:
        raise BadArgs

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
        spin.addr(chip_x, chip_y, chip_p)


def cmd_sver(cmd):
    if cmd.count:
        raise BadArgs
    print(spin.ver())


def cmd_lw(cmd):
    if cmd.count < 2 or cmd.count > 3:
        raise BadArgs
    link = cmd.arg(0)
    addr = cmd.arg(1)

    if cmd.count == 2:
        data = struct.unpack("<I", spin.link_read(link, addr, 4))
        print("{:08x} = {:08x}".format(addr, data[0]))
    else:
        data = struct.pack("<I", cmd.arg(2))
        spin.link_write(link, addr, data)


def cmd_lmemw(cmd):
    if cmd.count != 2:
        raise BadArgs
    link = cmd.arg(0)
    addr = cmd.arg(1)
    data = spin.link_read(link, addr, 256)
    hex_dump(data, addr=addr, format="word")


def cmd_smemw(cmd):
    if cmd.count > 1:
        raise BadArgs
    addr = cmd.arg(0) if cmd.count else 0
    data = spin.read(addr, 256, type="word")
    hex_dump(data, addr=addr, format="word")


def cmd_smemh(cmd):
    if cmd.count > 1:
        raise BadArgs
    addr = cmd.arg(0) if cmd.count else 0
    data = spin.read(addr, 256, type="half")
    hex_dump(data, addr=addr, format="half", width=16)


def cmd_smemb(cmd):
    if cmd.count > 1:
        raise BadArgs
    addr = cmd.arg(0) if cmd.count else 0
    data = spin.read(addr, 256, type="byte")
    hex_dump(data, addr=addr)


#-------------------------------------------------------------------------------


def cmd_expert(cmd):
    if cmd.count:
        raise BadArgs
    global expert

    if expert:
        return
    expert = True
    cli.cmd(expert_cmds, 0)

    print("# You are now an expert!")


#-------------------------------------------------------------------------------


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
