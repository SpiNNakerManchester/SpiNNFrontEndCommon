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
import os
import re
import struct

_RANGE_RE = re.compile(r"^(\d+)(?:-(\d+))?$")
_REGION_RE = re.compile(r"^(\d+),(\d+)$")


# pylint: disable=redefined-builtin
def hex_dump(data, *, format="byte",  # @ReservedAssignment
             width=None, addr=0, start=0, length=None, prefix="",
             do_print=True):
    """
    Convert a block of data into human-readable string form.

    :param bytes data:
        The block of data to render
    :return:
        The human-readable version, if not directly printed
    :rtype: str
    :keyword str format:
        ``byte`` or ``half`` or ``word``
    :keyword int width:
        Number of bytes per output line
    :keyword int addr:
        The start address of the block
    :keyword int start:
        Where in the block to start printing from
    :keyword int length:
        The actual length of the data, if not just the whole buffer
    :keyword str prefix:
        String to put at the start of each line
    :keyword bool do_print:
        Whether to directly print the data
    """
    width = width if width is not None else 16 if format == "byte" else 32
    count = length if length is not None else len(data)

    result = ""
    ptr = start
    while count:
        chunk = data[ptr:ptr + min(width, count) - 1]
        if not len(chunk):
            break

        text = f"{prefix}0{addr + ptr}x "

        if format == "byte":
            ds = struct.unpack(f"<{len(chunk)}B", chunk)
            for d in ds:
                text += f" {d:02x}"
            text += "   " * (width - len(ds))
            text += "  "
            for d in ds:
                text += struct.pack("c", d) if 32 <= d < 127 else "."
        elif format == "half":
            for d in struct.unpack(f"<{len(chunk) // 2}H", chunk):
                text += f" {d:04x}"
        elif format == "word":
            for d in struct.unpack(f"<{len(chunk) // 4}I", chunk):
                text += f" {d:08x}"

        if do_print:
            print(text)
        else:
            result += text
            result += "\n"
        ptr += len(chunk)
        count -= len(chunk)
    return result


def parse_apps(apps):
    """
    Parse an application ID or ID range.

    :param str apps: The user-specified string
    :return: The inclusive endpoints of the range
    :rtype: tuple(int,int)
    :raises ValueError: On bad input
    """
    m = _RANGE_RE.match(apps)
    if not m:
        raise ValueError("bad app specifier")
    app_id, max_id = m.groups()
    app_id = int(app_id)

    if max_id is None:
        if 0 <= app_id < 256:
            return app_id, 255
        raise ValueError("bad app specifier")

    id_range = int(max_id) - app_id + 1
    if id_range < 1 or app_id % id_range != 0 or app_id + id_range > 256:
        raise ValueError("bad app specifier")
    app_mask = 255 & ~(id_range - 1)
    return app_id, app_mask


def parse_bits(mask, minimum, maximum):
    """
    Parse a collection of bits and bit ranges into a bit mask.

    :param str mask: the mask description string from the user
    :param int minimum: the minimum value of bit ID
    :param int maximum: the maximum value of bit ID
    :return: the combined bit mask
    :rtype: int
    """
    if mask is None:
        raise ValueError("bad mask specifier")
    elif "all" == mask:
        mask = f"{minimum}-{maximum}"

    r = 0
    for sub in mask.split(","):
        m = _RANGE_RE.match(sub)
        if not m:
            raise ValueError("bad mask specifier")
        _from, _to = m.groups()
        _from = int(_from)
        if _to is None:
            if not minimum <= sub <= maximum:
                raise ValueError("bad mask specifier: out of range")
            r |= 1 << sub
        else:
            _to = int(_to)
            if not minimum <= _from <= _to <= maximum:
                raise ValueError("bad mask specifier: out of range")
            for i in range(_from, _to + 1):
                r |= 1 << i
    return r


def parse_cores(mask):
    """
    Parse a collection of bits and bit ranges into a bit mask selecting
    application cores.

    :param str mask: the mask description string from the user
    :return: the combined bit mask
    :rtype: int
    """
    return parse_bits(mask, 1, 17)


def parse_region(region, x, y):
    """
    Parse a board region description.

    :param str region:
        ``.`` or ``x,y`` (e.g., ``3,4``) or ``all``
        or ``a`` (``a`` = integer in 0..15) or ``a.b`` or ``a.b.c``
    :param int x: Default x
    :param int y: Default y
    :return: region descriptor
    :rtype: int
    """
    if region is None:
        raise ValueError("bad region specifier")

    if region == ".":
        if x is None or y is None:
            raise ValueError("incomplete region data")
        m = (y & 3) << 2 | (x & 3)
        return ((x & 0xFC) << 24) | ((y & 0xFC) << 16) | (3 << 16) | (1 << m)

    m = _REGION_RE.match(region)
    if m:
        x, y = map(int, m.groups())
        m = (y & 3) * 4 + (x & 3)
        return ((x & 0xFC) << 24) | ((y & 0xFC) << 16) | (3 << 16) | (1 << m)

    if region.lower() == "all":
        # Is this right?
        region = "0-15"

    regions = region.split(".")
    level = len(regions) - 1
    if level > 3:
        raise ValueError("too many region levels")

    x, y = 0, 0
    for i, d in enumerate(regions):
        if i == level:
            break
        d = int(d)
        if not 0 <= d <= 15:
            raise ValueError("bad region data")
        shift = 6 - 2 * i
        x |= (d & 3) << shift
        y |= (d >> 2) << shift
    mask = parse_bits(regions[-1], 0, 15)
    return (x << 24) | (y << 16) | (level << 16) | mask


def read_file(filename, max_size=0):
    """ Read a file.

    :param str filename:
        The name of the file to read
    :param int max_size:
        If given, the max size of file that will be read
    :return: The byte content of the file
    :rtype: bytes
    :raises ValueError:
        If a max size is given and the file is too large.
    """
    with open(filename, "rb") as f:
        if max_size and os.fstat(f.fileno()).st_size > max_size:
            raise ValueError("file too large")
        return f.read()


def find_path(filename):
    """ Locate a file on the ``SPINN_PATH``.

    :param str filename:
        The filename to locate
    :return: The located filename
    :rtype: str
    :raises ValueError:
        If the file can't be found.
    """
    currentdir = os.path.dirname(os.path.abspath(__file__))
    file_in_bootdir = os.path.join(currentdir, "boot", filename)
    if os.path.exists(file_in_bootdir):
        return os.path.normpath(file_in_bootdir)

    spinn_path = os.environ["SPINN_PATH"]
    for d in spinn_path.split(os.pathsep):
        file_on_path = os.path.join(d, filename)
        if os.path.exists(file_on_path):
            return os.path.normpath(file_on_path)

    raise ValueError(f"{filename} not found!")


def read_path(filename, max_size=0):
    """ Locate and read a file on the ``SPINN_PATH``.

    :param str filename:
        The filename to locate
    :param int max_size:
        If given, the max size of file that will be read
    :return: The byte content of the file
    :rtype: bytes
    :raises ValueError:
        If the file can't be found, or
        if it is too large (if a max size is given).
    """
    return read_file(find_path(filename), max_size)
