# Copyright (c) 2014 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from decimal import Decimal
from enum import Enum
import struct
from typing import Any, Callable, Optional, Union, cast
import numpy as np
from numpy.typing import NDArray
from numpy import uint32


class DataType(Enum):
    """
    Supported data types.
    Internally, these are actually tuples.

    #. an identifier for the enum class;
    #. the size in bytes of the type;
    #. the minimum possible value for the type;
    #. the maximum possible value for the type;
    #. the scale of the input value to convert it in integer;
    #. the pattern to use following the struct package encodings to convert
       the data in binary format;
    #. is whether to apply the scaling when converting to SpiNNaker's binary
       format.
    #. the corresponding numpy type (or None to inhibit direct conversion via
       numpy, scaled conversion still supported);
    #. the text description of the type.

    .. note::
        Some types (notably 64-bit fixed-point and floating-point types) are
        not recommended for use on SpiNNaker due to complications with
        represent them and lack of hardware/library support.
    """
    #: 8-bit unsigned integer
    UINT8: 'DataType' = cast('DataType', (
        0,
        1,
        Decimal("0"),
        Decimal("255"),
        Decimal("1"),
        "B",
        False,
        int,
        np.uint8,
        "8-bit unsigned integer"))
    #: 16-bit unsigned integer
    UINT16: 'DataType' = cast('DataType', (
        1,
        2,
        Decimal("0"),
        Decimal("65535"),
        Decimal("1"),
        "H",
        False,
        int,
        np.uint16,
        "16-bit unsigned integer"))
    #: 32-bit unsigned integer
    UINT32: 'DataType' = cast('DataType', (
        2,
        4,
        Decimal("0"),
        Decimal("4294967295"),
        Decimal("1"),
        "I",
        False,
        int,
        uint32,
        "32-bit unsigned integer"))
    #: 64-bit unsigned integer
    UINT64: 'DataType' = cast('DataType', (
        3,
        8,
        Decimal("0"),
        Decimal("18446744073709551615"),
        Decimal("1"),
        "Q",
        False,
        int,
        np.uint64,
        "64-bit unsigned integer"))
    #: 8-bit signed integer
    INT8: 'DataType' = cast('DataType', (
        4,
        1,
        Decimal("-128"),
        Decimal("127"),
        Decimal("1"),
        "b",
        False,
        int,
        np.int8,
        "8-bit signed integer"))
    #: 16-bit signed integer
    INT16: 'DataType' = cast('DataType', (
        5,
        2,
        Decimal("-32768"),
        Decimal("32767"),
        Decimal("1"),
        "h",
        False,
        int,
        np.int16,
        "16-bit signed integer"))
    #: 32-bit signed integer
    INT32: 'DataType' = cast('DataType', (
        6,
        4,
        Decimal("-2147483648"),
        Decimal("2147483647"),
        Decimal("1"),
        "i",
        False,
        int,
        np.int32,
        "32-bit signed integer"))
    #: 64-bit signed integer
    INT64: 'DataType' = cast('DataType', (
        7,
        8,
        Decimal("-9223372036854775808"),
        Decimal("9223372036854775807"),
        Decimal("1"),
        "q",
        False,
        int,
        np.int64,
        "64-bit signed integer"))
    #: 8.8 unsigned fixed point number
    U88: 'DataType' = cast('DataType', (
        8,
        2,
        Decimal("0"),
        Decimal("255.99609375"),
        Decimal("256"),
        "H",
        True,
        None,
        np.uint16,
        "8.8 unsigned fixed point number"))
    #: 16.16 unsigned fixed point number
    U1616: 'DataType' = cast('DataType', (
        9,
        4,
        Decimal("0"),
        Decimal("65535.9999847"),
        Decimal("65536"),
        "I",
        True,
        None,
        uint32,
        "16.16 unsigned fixed point number"))
    #: 32.32 unsigned fixed point number
    #: (use *not* recommended: representability)
    U3232: 'DataType' = cast('DataType', (
        10,
        8,
        Decimal("0"),
        Decimal("4294967295.99999999976716935634613037109375"),
        Decimal("4294967296"),
        "Q",
        True,
        None,
        np.uint64,
        "32.32 unsigned fixed point number"))  # rounding problem for max
    #: 8.7 signed fixed point number
    S87: 'DataType' = cast('DataType', (
        11,
        2,
        Decimal("-256"),
        Decimal("255.9921875"),
        Decimal("128"),
        "h",
        True,
        None,
        np.int16,
        "8.7 signed fixed point number"))
    #: 16.15 signed fixed point number
    S1615: 'DataType' = cast('DataType', (
        12,
        4,
        Decimal("-65536"),
        Decimal("65535.999969482421875"),
        Decimal("32768"),
        "i",
        True,
        None,
        np.int32,
        "16.15 signed fixed point number"))
    #: 32.31 signed fixed point number
    #: (use *not* recommended: representability)
    S3231: 'DataType' = cast('DataType', (
        13,
        8,
        Decimal("-4294967296"),
        Decimal("4294967295.9999999995343387126922607421875"),
        Decimal("2147483648"),
        "q",
        True,
        None,
        np.int64,
        "32.31 signed fixed point number"))  # rounding problem for max
    #: 32-bit floating point number
    FLOAT_32: 'DataType' = cast('DataType', (
        14,
        4,
        Decimal("-3.4028234e38"),
        Decimal("3.4028234e38"),
        Decimal("1"),
        "f",
        False,
        float,
        np.float32,
        "32-bit floating point number"))
    #: 64-bit floating point number
    #: (use *not* recommended: hardware/library support inadequate)
    FLOAT_64: 'DataType' = cast('DataType', (
        15,
        8,
        Decimal("-1.7976931348623157e+308"),
        Decimal("1.7976931348623157e+308"),
        Decimal("1"),
        "d",
        False,
        float,
        np.float64,
        "64-bit floating point number"))
    #: 0.8 unsigned fixed point number
    U08: 'DataType' = cast('DataType', (
        16,
        1,
        Decimal("0"),
        Decimal("0.99609375"),
        Decimal("256"),
        "B",
        True,
        None,
        np.uint16,
        "0.8 unsigned fixed point number"))
    #: 0.16 unsigned fixed point number
    U016: 'DataType' = cast('DataType', (
        17,
        2,
        Decimal("0"),
        Decimal("0.999984741211"),
        Decimal("65536"),
        "H",
        True,
        None,
        np.uint16,
        "0.16 unsigned fixed point number"))
    #: 0.32 unsigned fixed point number
    U032: 'DataType' = cast('DataType', (
        18,
        4,
        Decimal("0"),
        Decimal("0.99999999976716935634613037109375"),
        Decimal("4294967296"),
        "I",
        True,
        None,
        uint32,
        "0.32 unsigned fixed point number"))
    #: 0.64 unsigned fixed point number
    #: (use *not* recommended: representability)
    U064: 'DataType' = cast('DataType', (
        19,
        8,
        Decimal("0"),
        Decimal("0.9999999999999999999457898913757247782996273599565029"),
        Decimal("18446744073709551616"),
        "Q",
        True,
        None,
        np.uint64,
        "0.64 unsigned fixed point number"))  # rounding problem for max
    #: 0.7 signed fixed point number
    S07: 'DataType' = cast('DataType', (
        20,
        1,
        Decimal("-1"),
        Decimal("0.9921875"),
        Decimal("128"),
        "b",
        True,
        None,
        np.int8,
        "0.7 signed fixed point number"))
    #: 0.15 signed fixed point number
    S015: 'DataType' = cast('DataType', (
        21,
        2,
        Decimal("-1"),
        Decimal("0.999969482421875"),
        Decimal("32768"),
        "h",
        True,
        None,
        np.int16,
        "0.15 signed fixed point number"))
    #: 0.32 signed fixed point number
    S031: 'DataType' = cast('DataType', (
        22,
        4,
        Decimal("-1"),
        Decimal("0.99999999976716935634613037109375"),
        Decimal("2147483648"),
        "i",
        True,
        None,
        np.int32,
        "0.32 signed fixed point number"))
    #: 0.63 signed fixed point number
    #: (use *not* recommended: representability)
    S063: 'DataType' = cast('DataType', (
        23,
        8,
        Decimal("-1"),
        Decimal("0.9999999999999999998915797827514495565992547199130058"),
        Decimal("9223372036854775808"),
        "q",
        True,
        None,
        np.int64,
        "0.63 signed fixed point number"))  # rounding problem for max

    def __new__(cls, *args) -> 'DataType':
        # pylint: disable=protected-access, too-many-arguments
        obj = object.__new__(cls)
        obj._value_ = args[0]
        obj.__doc__ = args[-1]
        return obj

    def __init__(self, __, size: int, min_val: Decimal, max_val: Decimal,
                 scale: Decimal, struct_encoding: str, apply_scale: bool,
                 force_cast: Optional[Callable[[Any], int]],
                 numpy_typename: type, _doc: str = ""):
        # pylint: disable=protected-access, too-many-arguments
        self._size = size
        self._min = min_val
        self._max = max_val
        self._scale = scale
        self._struct_encoding = struct_encoding
        self._numpy_typename = numpy_typename
        self._apply_scale = apply_scale
        self._force_cast = force_cast
        self._struct = struct.Struct("<" + struct_encoding)
        if size == 1:
            struct_encoding += "xxx"
        elif size == 2:
            struct_encoding += "xx"

    @property
    def size(self) -> int:
        """
        The size in bytes of the type.

        :rtype: int
        """
        return self._size

    @property
    def min(self) -> Decimal:
        """
        The minimum possible value for the type.

        :rtype: ~decimal.Decimal
        """
        return self._min

    @property
    def max(self) -> Decimal:
        """
        The maximum possible value for the type.

        :rtype: ~decimal.Decimal
        """
        return self._max

    def check_value(self, value: Union[int, float]):
        """
        Check the value against the allowed min and max

        :type value: float or int
        :raises ValueError: If the value is outside of min to max
        """
        if value < self.min:
            raise ValueError(
                f"Value {value} is smaller than the minimum {self.min} "
                f"allowed for a {self}")
        if value > self.max:
            raise ValueError(
                f"Value {value} is greater than the maximum {self.max} "
                f"allowed for a {self}")

    @property
    def scale(self) -> Decimal:
        """
        The scale of the input value to convert it in integer.

        :rtype: ~decimal.Decimal
        """
        return self._scale

    @property
    def struct_encoding(self) -> str:
        """
        The encoding string used for struct. Scaling may also be required.

        :rtype: str
        """
        return self._struct_encoding

    @property
    def numpy_typename(self) -> type:
        """
        The corresponding numpy type, if one exists.
        """
        return self._numpy_typename

    def encode_as_int(self, value: Union[int, float]) -> int:
        """
        Returns the value as an integer, according to this type.

        :param value:
        :type value: float or int
        :rtype: int
        """
        if self._apply_scale:
            # Deal with the cases that return np.int64  or np.int32
            # (e.g. RandomDistribution when using 'poisson', 'binomial' etc.)
            # The less than raises TypeError even with int32 on some numpy
            if isinstance(value, np.integer):
                value = int(value)
            if not (self._min <= value <= self._max):
                raise ValueError(
                    f"value {value:f} cannot be converted to {self.__doc__}"
                    ": out of range")
            return int(round(Decimal(str(value)) * self._scale))
        if self._force_cast is not None:
            return self._force_cast(value)
        return cast(int, value)

    def encode_as_numpy_int(self, value: Union[int, float]) -> uint32:
        """
        Returns the value as a numpy integer, according to this type.

        .. note::
            Only works with integer and fixed point data types.

        :param value:
        :type value: float or int
        :rtype: ~numpy.uint32
        """
        return np.round(self.encode_as_int(value)).astype(self.struct_encoding)

    def encode_as_numpy_int_array(self, array: NDArray) -> NDArray:
        """
        Returns the numpy array as an integer numpy array, according to
        this type.

        :param ~numpy.ndarray array:
        :rtype: ~numpy.ndarray
        """
        if self._apply_scale:
            # pylint: disable=assignment-from-no-return
            where = np.logical_or(array < self._min, self._max < array)
            if where.any():
                raise ValueError(
                    f"value {array[where][0]:f} cannot be converted to "
                    f"{self.__doc__}: out of range")
            return np.round(array * float(self._scale)).astype(uint32)
        if self._force_cast is not None:
            return np.array([self._force_cast(x) for x in array]).astype(
                uint32)
        return np.array(array)

    def as_bytes(self, value: Union[int, float]) -> bytes:
        """
        Encode the Python value as bytes with NO padding.

        :param value:
        :type value: float or int
        :rtype: bytes
        """
        return self._struct.pack(self.encode_as_int(value))

    def decode_numpy_array(self, array: NDArray[uint32]) -> NDArray:
        """
        Decode the numpy array of SpiNNaker values according to this type.

        :param ~numpy.ndarray(~numpy.uint32) array:
        :rtype: ~numpy.ndarray(~numpy.uint32 or ~numpy.float64)
        """
        return array / float(self._scale)

    def decode_array(self, values: Union[NDArray, bytes]) -> NDArray:
        """
        Decodes a byte array into iterable of this type.

        :param values: the bytes to decode into this given data type
        :rtype: numpy array
        """
        array: np.ndarray = np.asarray(values, dtype="uint8").view(
            dtype=self.numpy_typename)
        if self._apply_scale:
            return array / float(self.scale)
        return array
