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
import re
import struct
from collections import namedtuple
from tools.exn import StructParseException
from tools.util import find_path


Field = namedtuple("Field", ["pack", "offset", "fmt", "index", "size"])


class _Struct(object):
    __slots__ = ("size", "base", "__fields", "__values")

    _SIZE = {
        "V": 4,
        "v": 2,
        "C": 1,
        "A16": 16
    }

    _REPACK = {
        "V": "<I",
        "v": "<H",
        "C": "<B",
        "A16": "<16s"
    }

    def __init__(self):
        self.size = 0
        self.base = None
        self.__fields = dict()
        self.__values = dict()

    def __getitem__(self, name):
        return self.__fields[name]

    def __setitem__(self, name, value):
        self.__values[name] = value

    def add_field(self, field, value, pack, offset, fmt, index):
        size = self._SIZE[pack]
        pack = self._REPACK[pack]
        if fmt.endswith("x}"):
            fmt = "0x" + fmt
        self.__fields[field] = Field(pack, offset, fmt, index, size)
        self.__values[field] = value

    @property
    def fields(self):
        for f in self.__fields:
            yield f

    def value(self, field):
        return self.__values[field]


class Struct(object):
    """ Manages data in structs. """
    __slots__ = ("__scp", "__structs")

    _FIELD_MATCHER = re.compile(
        r"""(?x)^
        ([\w.]+)
        (?:\[ (\d+) \])? \s+
        (V|v|C|A16) \s+
        (\S+) \s+
        %(\d*[dxs]) \s+
        (\S+)
        $""")

    def __init__(self, scp, filename="sark.struct", debug=False):
        self.__scp = scp
        self.__structs = {}
        self.read_file(filename, debug)

    def __parse_field(self, line, struct_name, file_name, line_number):
        m = self._FIELD_MATCHER.match(line)
        if not m:
            return False

        field, index, pack, offset, fmt, value = m.groups()
        try:
            offset = int(offset, base=0)
            value = int(value, base=0)
        except ValueError:
            raise StructParseException(
                "read_file: syntax error - {}.{}".format(
                    file_name, line_number))

        index = 1 if index is None else int(index)
        self.__structs[struct_name].add_field(
            field, value, pack, offset, re.sub(r"(.+)", r"{:\1}", fmt), index)
        return True

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
                        if not self.__structs[name].size:
                            raise StructParseException(
                                "read_file: size undefined in {}".format(
                                    filename))
                        if self.__structs[name].base is None:
                            raise StructParseException(
                                "read_file: base undefined in {}".format(
                                    filename))
                    name = m.group(1)
                    self.__structs[name] = _Struct()
                    continue

                m = re.match(r"^size\s*=\s*(\S+)$", line)
                if m:
                    self.__structs[name].size = int(m.group(1), base=0)
                    continue

                m = re.match(r"base\s*=\s*(\S+)$", line)
                if m:
                    self.__structs[name].base = int(m.group(1), base=0)
                    continue

                if self.__parse_field(line, name, filename, line_number):
                    continue

                raise StructParseException(
                    "read_file: syntax error - {}.{}".format(
                        filename, line_number))
        if debug:
            print(">> EOF")
            for n in self.__structs:
                print(">> {} {}".format(n, self.__structs[n]))

    def __read(self, *args, **kwargs):
        if self.__scp is None:
            raise RuntimeError("not bound to existing SpiNNaker instance")
        return self.__scp.read(*args, **kwargs)

    def __write(self, *args, **kwargs):
        if self.__scp is None:
            raise RuntimeError("not bound to existing SpiNNaker instance")
        return self.__scp.write(*args, **kwargs)

    def read_struct(self, name, addr=None):
        sv = self.__structs[name]
        self.unpack(name, self.__read(sv.base, sv.size, addr=addr))

    def write_struct(self, name, addr=None):
        data = self.pack(name)
        sv = self.__structs[name]
        self.__write(sv.base, sv.size, data, addr=addr)

    def read_var(self, var, addr=None):
        name, field = var.split(".")
        sv = self.__structs[name]
        f = sv[field]
        data, = struct.unpack(f.pack, self.__read(
            sv.base + f.offset, f.size, addr=addr))
        sv[field] = data
        return data

    def write_var(self, var, new, addr=None):
        name, field = var.split(".")
        sv = self.__structs[name]
        f = sv[field]
        self.__write(
            sv.base + f.offset, struct.pack(f.pack, new), addr=addr)
        sv[field] = new

    def pack(self, name):
        sv = self.__structs[name]
        data = b'\0' * sv.size
        for field in sv.fields:
            f = sv[field]
            struct.pack_into(f.pack, data, f.offset, sv.value(field))
        return data

    def unpack(self, name, data):
        sv = self.__structs[name]
        for field in sv.fields:
            f = sv[field]
            values = struct.unpack_from(f.pack, data, f.offset)
            sv[field] = values[0]

    def dump(self, name):
        sv = self.__structs[name]
        fields = list(sv.fields)
        fields.sort(key=lambda f: sv[f].offset)
        for field in fields:
            print(("{:<16s} " + sv[field].fmt).format(field, sv.value(field)))

    def size(self, name):
        return self.__structs[name].size

    def base(self, name, new=None):
        sv = self.__structs[name]
        old = sv.base
        if new is not None:
            sv.base = new
        return old

    def addr(self, name, field):
        sv = self.__structs[name]
        return sv.base + sv[field].offset

    def get_var(self, var):
        name, field = var.split(".")
        sv = self.__structs[name]
        return sv.value(field)

    def set_var(self, var, value):
        name, field = var.split(".")
        sv = self.__structs[name]
        old = sv.value(field)
        sv[field] = value
        return old

    def update(self, name, filename):
        raise NotImplementedError
