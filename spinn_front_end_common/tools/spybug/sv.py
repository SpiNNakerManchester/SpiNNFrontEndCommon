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
from typing import NamedTuple
from .exn import StructParseException
from .util import find_path


class Field(NamedTuple):
    pack: str
    offset: int
    fmt: str
    index: int
    size: int


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

    def __getitem__(self, name) -> Field:
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

    def __init__(self, scp, *, filename="sark.struct", debug=False):
        """
        :param SCAMPCmd scp:
            How to talk to SCAMP about the structure
        :keyword str filename:
            Where to load the structure definition from
        :keyword bool debug:
            Whether to print debugging messages
        """
        self.__scp = scp
        self.__structs = {}
        self.read_file(filename, debug=debug)

    def __parse_field(self, line, struct_name, file_name, line_number):
        m = self._FIELD_MATCHER.match(line)
        if not m:
            return False

        field, index, pack, offset, fmt, value = m.groups()
        try:
            offset = int(offset, base=0)
            value = int(value, base=0)
        except ValueError as e:
            raise StructParseException(
                f"read_file: syntax error - {file_name}.{line_number}") from e

        index = 1 if index is None else int(index)
        self.__s(struct_name).add_field(
            field, value, pack, offset, re.sub(r"(.+)", r"{:\1}", fmt), index)
        return True

    def __s(self, name):
        """
        :param str name:
        :rtype: _Struct
        """
        return self.__structs[name]

    def read_file(self, filename, *, debug=False):
        """ Parse a structure definition file.

        :param str filename:
            The name of the file to load
        :keyword bool debug:
            Whether to print debugging messages
        """
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
                    self.read_file(m.group(1), debug=debug)
                    return

                if debug:
                    print(f">> {line}")

                m = re.match(r"^name\s*=\s*(\w+)$", line)
                if m:
                    if name:
                        if not self.__s(name).size:
                            raise StructParseException(
                                f"read_file: size undefined in {filename}")
                        if self.__s(name).base is None:
                            raise StructParseException(
                                f"read_file: base undefined in {filename}")
                    name = m.group(1)
                    self.__structs[name] = _Struct()
                    continue

                if not name:
                    raise StructParseException(
                        f"read_file: name undefined in {filename}")
                m = re.match(r"^size\s*=\s*(\S+)$", line)
                if m:
                    self.__s(name).size = int(m.group(1), base=0)
                    continue

                m = re.match(r"base\s*=\s*(\S+)$", line)
                if m:
                    self.__s(name).base = int(m.group(1), base=0)
                    continue

                if self.__parse_field(line, name, filename, line_number):
                    continue

                raise StructParseException(
                    f"read_file: syntax error - {filename}.{line_number}")
        if debug:
            print(">> EOF")
            for n in self.__structs:
                print(f">> {n} {self.__s(n)}")

    def __read(self, base, length, addr):
        if self.__scp is None:
            raise RuntimeError("not bound to existing SpiNNaker instance")
        return self.__scp.read(base, length, addr=addr)

    def __write(self, base, data, addr):
        if self.__scp is None:
            raise RuntimeError("not bound to existing SpiNNaker instance")
        return self.__scp.write(base, data, addr=addr)

    def read_struct(self, name, *, addr=None):
        """
        Read the named structure from the SpiNNaker machine

        :param str name: Which structure to read
        :keyword addr: Which core to read the structure from
        """
        sv = self.__s(name)
        self.unpack(name, self.__read(sv.base, sv.size, addr))

    def write_struct(self, name, *, addr=None):
        """
        Write the named structure to the SpiNNaker machine

        :param str name: Which structure to write
        :keyword addr: Which core to write the structure to
        """
        data = self.pack(name)
        sv = self.__s(name)
        self.__write(sv.base, data, addr)

    def read_var(self, var, *, addr=None):
        """
        Read the named field of a structure from the SpiNNaker machine

        :param str name: Which field to read; format ``structname.fieldname``
        :keyword addr: Which core to read the field from
        :rtype: int
        """
        name, field = var.split(".")
        sv: _Struct = self.__s(name)
        f: Field = sv[field]
        data, = struct.unpack(f.pack, self.__read(
            sv.base + f.offset, f.size, addr))
        sv[field] = data
        return data

    def write_var(self, var, new, *, addr=None):
        """
        Write the named field of a structure to the SpiNNaker machine

        :param str name: Which field to write; format ``structname.fieldname``
        :param int new: The new value of the field
        :keyword addr: Which core to write the field to
        """
        name, field = var.split(".")
        sv = self.__s(name)
        f = sv[field]
        self.__write(sv.base + f.offset, struct.pack(f.pack, new), addr)
        sv[field] = new

    def pack(self, name):
        """
        Construct the literal data representing the named structure

        :param str name: Which structure to pack
        :rtype: bytes
        """
        sv = self.__s(name)
        data = b'\0' * sv.size
        for field in sv.fields:
            f = sv[field]
            struct.pack_into(f.pack, data, f.offset, sv.value(field))
        return data

    def unpack(self, name, data):
        """
        Extract local cache values from literal data.

        :param str name: Which structure to unpack
        :param bytes data: What data to unpack
        """
        sv = self.__s(name)
        for field in sv.fields:
            f = sv[field]
            values = struct.unpack_from(f.pack, data, f.offset)
            sv[field] = values[0]

    def dump(self, name):
        """
        Print the content of a structure, in alphabetical order of fields

        :param str name: Which structure to print
        """
        sv = self.__s(name)
        fields = list(sv.fields)
        fields.sort(key=lambda f: sv[f].offset)
        for field in fields:
            print(("{:<16s} " + sv[field].fmt).format(field, sv.value(field)))

    def size(self, name):
        """
        Get the size of a structure

        :param str name: Which structure to get the size of
        :return: The size of the structure, in bytes
        :rtype: int
        """
        return self.__s(name).size

    def base(self, name, new=None):
        """ Get or set the base address of a structure

        :param str name: Which structure
        :param int new: The new base address, if setting
        :return: The base address (or old base address, if setting)
        :rtype: int
        """
        sv = self.__s(name)
        old = sv.base
        if new is not None:
            sv.base = new
        return old

    def addr(self, name, field):
        """ Get or set the base address of a structure

        :param str name: Which structure
        :param int new: The new base address, if setting
        :return: The base address (or old base address, if setting)
        :rtype: int
        """
        sv = self.__s(name)
        return sv.base + sv[field].offset

    def get_var(self, var):
        """ Get the cached value of a field of a structure

        :param str name: Which field to get; format ``structname.fieldname``
        :rtype: int
        """
        name, field = var.split(".")
        return self.__s(name).value(field)

    def set_var(self, var, value):
        """ Set the cached value of a field of a structure

        :param str name: Which field to set; format ``structname.fieldname``
        :param int value: What value to set
        :return: The old value of the field
        :rtype: int
        """
        name, field = var.split(".")
        sv = self.__s(name)
        old = sv.value(field)
        sv[field] = value
        return old

    def update(self, name, filename):
        """
        Load values for a structure from a file

        :param str name: Which structure
        :param str filename: Where to load values from.
            Each line of the file is a setting, being the field name, some
            whitespace, and the integer value.
        """
        sv = self.__s(name)
        with open(filename) as f:
            for line in f:
                field, value = line.split()
                sv[field] = int(value, 0)
