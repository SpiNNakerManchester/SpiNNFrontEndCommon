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
""" Boot a SpiNNaker system.
"""

import socket
import struct
import time
from tools.util import find_path, read_path
from tools.cmd import SCAMPCmd
from tools.sv import Struct

PROT_VER = 1
BOOT_BYTE_SIZE = 1024
MAX_BLOCKS = 32


def boot_pkt(sock, op, a1, a2, a3, data, delay):
    hdr = struct.pack(">H4I", PROT_VER, op, a1, a2, a3)
    if data:
        # Byte-swap the data; this protocol is BIG-ENDIAN!
        wordlen = len(data) // 4
        data = struct.pack(">{}I".format(wordlen),
                           *struct.unpack("<{}I".format(wordlen), data))
    sock.send(hdr + data)
    time.sleep(delay)


def rom_boot(host, buf, debug, port):
    """ Boot using SpiNNaker BootROM protocol.
    """
    delay = 0.01
    size = len(buf)
    blocks = size // BOOT_BYTE_SIZE
    if size % BOOT_BYTE_SIZE:
        blocks += 1

    if debug:
        print("Boot: {} bytes, {} blocks".format(size, blocks))
    if blocks > MAX_BLOCKS:
        raise ValueError("boot file too big")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((host, port))
        if debug:
            print("Boot: Start (delay {})".format(delay))
        boot_pkt(sock, 1, 0, 0, blocks - 1, b'', delay)

        for block in range(blocks):
            data = buf[block * BOOT_BYTE_SIZE:(block + 1) * BOOT_BYTE_SIZE]
            a1 = ((BOOT_BYTE_SIZE // 4 - 1) << 8) | (block & 0xFF)
            if debug:
                print("Boot: Data {}".format(block), end="\r")
            boot_pkt(sock, 3, a1, 0, 0, data, delay)

        if debug:
            print("\nBoot: End")
        boot_pkt(sock, 5, 1, 0, 0, b'', delay)

    time.sleep(2.0)


def scamp_boot(host, buf, sv, timestamp, debug):
    """ Boot using SpiNNaker SC&MP protocol.
    """
    spin = SCAMPCmd(target=host, debug=debug)
    try:
        if "SC&MP 0.91" not in spin.ver():
            raise RuntimeError("Expected SC&MP 0.91")
        spin.write(sv.addr("sv.ron_cpus"), b'\0')
        spin.flood_boot(buf)
        data, = spin.read(0xF5007F5C, 4, unpack="<I")
        if timestamp != data:
            raise RuntimeError("boot signature failure")
    finally:
        spin.close()


def boot(host, filename, conf, debug=0, port=54321):
    """ Main bootstrap routine.
    """
    sv = Struct(None)
    if conf:
        sv.update("sv", find_path(conf))
    buf = read_path(filename, 32768)

    timestamp = int(time.time())
    sv.set_var("sv.unix_time", timestamp)
    sv.set_var("sv.boot_sig", timestamp)

    if filename.endswith(".boot"):
        sv.set_var("sv.root_chip", 1)
        buf[384:512] = sv._pack("sv")[0:128]
        rom_boot(host, buf, debug, port)
    elif filename.endswith(".aplx"):
        sv.set_var("sv.boot_delay", 0)
        buf[384:512] = sv._pack("sv")[0:128]
        scamp_boot(host, buf, sv, timestamp, debug)
    else:
        raise ValueError("unknown boot file format")
