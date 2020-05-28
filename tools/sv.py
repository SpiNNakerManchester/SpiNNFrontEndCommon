import re
import struct
from collections import namedtuple
from tools.exn import StructParseException
from tools.util import find_path


Field = namedtuple("Field", ["pack", "offset", "fmt", "index", "size"])


class _Struct(object):
    __slots__ = ("_size", "_base", "_fields", "_values")

    _SIZE = {
        "V": 4,
        "v": 2,
        "C": 1,
        "A16": 16
    }

    _REPACK = {
        "V": "I",
        "v": "H",
        "C": "B",
        "A16": "16s"
    }

    def __init__(self):
        self._size = 0
        self._base = None
        self._fields = dict()
        self._values = dict()

    def __getitem__(self, name):
        return self._fields[name]

    def add_field(self, field, value, pack, offset, fmt, index):
        size = self._SIZE[pack]
        pack = self._REPACK[pack]
        if fmt.endswith("x"):
            fmt = "0x" + fmt
        fmt = re.sub(r"%(.+)", r"{:\1", fmt)
        self._fields[field] = Field(pack, offset, fmt, index, size)
        self._values[field] = value

    @property
    def fields(self):
        for f in self._fields:
            yield f

    def value(self, field):
        return self._values[field]


class Struct(object):
    """ Manages data in structs. """
    __slots__ = ("__scp", "__structs")

    def __init__(self, scp, filename="sark.struct", debug=False):
        self.__scp = scp
        self.__structs = {}
        self.read_file(filename, debug)

    def read_file(self, filename, debug=False):
        filename = find_path(filename)

        name = ""
        with open(filename) as f:
            line_number = 0
            for line in f:
                line_number += 1
                line = re.sub(r"#.*", "", line).strip()
                if not line:
                    continue

                m = re.match(r"^symlink\s+(.*)", line)
                if m:
                    self.read_file(m.group(1), debug)
                    return

                if debug:
                    print(">> {}".format(line))

                m = re.match(r"^name\s*=\s*(\w+)$", line)
                if m:
                    if name:
                        if not self.__structs[name]._size:
                            raise StructParseException(
                                "read_file: size undefined in {}".format(
                                    filename))
                        if self.__structs[name]._base is None:
                            raise StructParseException(
                                "read_file: base undefined in {}".format(
                                    filename))
                    name = m.group(1)
                    self.__structs[name] = _Struct()
                    continue

                m = re.match(r"^size\s*=\s*(\S+)$", line)
                if m:
                    self.__structs[name]._size = int(m.group(1), base=0)
                    continue

                m = re.match(r"base\s*=\s*(\S+)$", line)
                if m:
                    self.__structs[name]._base = int(m.group(1), base=0)
                    continue

                m = re.match(
                    r"^([\w\.]+)(?:\[(\d+)\])?\s+(V|v|C|A16)\s+(\S+)\s+(%\d*[dx]|%s)\s+(\S+)$",
                    line)
                if m:
                    field, index, pack, offset, fmt, value = m.groups()
                    try:
                        offset = int(offset, base=0)
                        value = int(value, base=0)
                    except ValueError:
                        raise StructParseException(
                            "read_file: syntax error - {}.{}".format(
                                filename, line_number))
                    if index is not None:
                        self.__structs[name].add_field(
                            field, value, pack, offset, fmt, int(index))
                    else:
                        self.__structs[name].add_field(
                            field, value, pack, offset, fmt, 1)
                    continue

                raise StructParseException(
                    "read_file: syntax error - {}.{}".format(
                        filename, line_number))
        if debug:
            print(">> EOF")
            for n in self.__structs:
                print(">> {} {}".format(n, self.__structs[n]))

    def read_struct(self, name, addr=None):
        sv = self.__structs[name]
        self._unpack(name, self.__scp.read(sv._base, sv._size, addr=addr))

    def write_struct(self, name, addr=None):
        data = self._pack(name)
        sv = self.__structs[name]
        self.__scp.write(sv._base, sv._size, data, addr=addr)

    def read_var(self, var, addr=None):
        name, field = var.split(".")
        sv = self.__structs[name]
        f = sv[field]
        base = sv._base + f.offset
        data = struct.unpack("<" + f.pack, self.__scp.read(
            base, f.size, addr=addr))
        sv.set_field_value(field, data[0])
        return data[0]

    def write_var(self, var, new, addr=None):
        name, field = var.split(".")
        sv = self.__structs[name]
        f = sv[field]
        base = sv._base + f.offset
        value = struct.pack(f.pack, new)
        self.__scp.write(base, value, addr=addr)
        sv.set_field_value(field, new)

    def _pack(self, name):
        sv = self.__structs[name]
        data = b'\0' * sv._size
        for field in sv.fields:
            f = sv[field]
            struct.pack_into(f.pack, data, f.offset, sv.value(field))
        return data

    def _unpack(self, name, data):
        sv = self.__structs[name]
        for field in sv.fields:
            f = sv[field]
            values = struct.unpack_from("<" + f.pack, data, f.offset)
            sv.set_field_value(field, values[0])

    def dump(self, name):
        sv = self.__structs[name]
        fields = list(sv.fields)
        fields.sort(key=lambda f: sv[f].offset)
        for field in fields:
            print(("{:-16s} " + sv[field].fmt).format(field, sv.value(field)))

    def size(self, name):
        sv = self.__structs[name]
        return sv._size

    def base(self, name, new=None):
        sv = self.__structs[name]
        old = sv._base
        if new != None:
            sv._base = new
        return old

    def addr(self, name, field):
        sv = self.__structs[name]
        return sv._base + sv[field].offset

    def get_var(self, var):
        name, field = var.split(".")
        sv = self.__structs[name]
        return sv.value(field)

    def set_var(self, var, value):
        name, field = var.split(".")
        sv = self.__structs[name]
        old = sv.value(field)
        sv.set_field_value(field, value)
        return old

    def update(self, name, filename):
        raise NotImplementedError
