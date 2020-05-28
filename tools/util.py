import os
import re
import struct

_RANGE_RE = re.compile(r"^(\d+)(?:-(\d+))?$")
_REGION_RE = re.compile(r"^(\d+),(\d+)$")


def hex_dump(data, format="byte",  # @ReservedAssignment
             width=None, addr=0, start=0, length=None, prefix=""):
    width = width if width is not None else 16 if format == "byte" else 32
    count = length if length is not None else len(data)

    ptr = start
    while count:
        chunk = data[ptr:ptr + min(width, count) - 1]
        if not len(chunk):
            break

        text = "{}0{}x ".format(prefix, addr + ptr)

        if format == "byte":
            ds = struct.unpack("<{}B".format(len(chunk)), chunk)
            for d in ds:
                text += " {:02x}".format(d)
            text += "   " * (width - len(ds))
            text += "  "
            for d in ds:
                text += struct.pack("c", d) if 32 <= d < 127 else "."
        elif format == "half":
            for d in struct.unpack("<{}H".format(len(chunk) // 2), chunk):
                text += " {:04x}".format(d)
        elif format == "word":
            for d in struct.unpack("<{}I".format(len(chunk) // 4), chunk):
                text += " {:08x}".format(d)

        print(text)
        ptr += len(chunk)
        count -= len(chunk)


def parse_apps(apps):
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
    if mask is None:
        raise ValueError("bad mask specifier")
    elif "all" == mask:
        mask = "{}-{}".format(minimum, maximum)

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
    return parse_bits(mask, 1, 17)


def parse_region(region, x, y):
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
    with open(filename, "rb") as f:
        if max_size and os.fstat(f.fileno()).st_size > max_size:
            raise ValueError("file too large")
        return f.read()


def find_path(filename):
    currentdir = os.path.dirname(os.path.abspath(__file__))
    file_in_bootdir = os.path.join(currentdir, "boot", filename)
    if os.path.exists(file_in_bootdir):
        return os.path.normpath(file_in_bootdir)

    spinn_path = os.environ["SPINN_PATH"]
    for d in spinn_path.split(os.pathsep):
        file_on_path = os.path.join(d, filename)
        if os.path.exists(file_on_path):
            return os.path.normpath(file_on_path)

    raise ValueError("{} not found!".format(filename))


def read_path(filename, max_size=0):
    return read_file(find_path(filename), max_size)


def bmp_version():
    pass  # TODO


def sllt_version():
    pass  # TODO
