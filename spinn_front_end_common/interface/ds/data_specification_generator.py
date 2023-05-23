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

import numpy
from data_specification.enums.data_type import DataType
from data_specification.exceptions import (
    InvalidSizeException, NotAllocatedException,
    NoRegionSelectedException, ParameterOutOfBoundsException,
    RegionInUseException, RegionUnfilledException, TypeMismatchException,
    UnknownTypeException, UnknownTypeLengthException)

BYTES_PER_WORD = 4


class DataSpecificationGenerator(object):
    """
    Used to generate the data specification data in the database
    """

    __slots__ = [
        "_core_id",
        "_data",
        "_data_debug",
        "_ds_db",
        "_offset",
        "_report_writer",
        "_region_id",
    ]

    def __init__(self, x, y, p, vertex, ds_db, report_writer=None):
        """

        :param int x:
        :param int y:
        :param int p:
        :param vertex:
        :type vertex:
            ~spinn_front_end_common.abstract_models.AbstractRewritesDataSpecification
        :type  ds_db:
            ~spinn_front_end_common.interface.ds.DataSpecificationGenerator
        :param report_writer:
            Determines if a text version of the specification is to be
            written and, if so, where. No report is written if this is `None`.
        :type report_writer: ~io.TextIOBase or None
        """
        self._ds_db = ds_db
        self._report_writer = report_writer
        self._core_id = ds_db.get_core_id(x, y, p, vertex)
        self._region_id = None
        self._data = None
        self._data_debug = None
        self._offset = None

    def comment(self, comment):
        """
        Write a comment to the text version of the specification.

        .. note::
            This is ignored by the binary file.

        :param str comment: The comment to write
        """
        if self._report_writer is not None:
            self._report_writer.write(comment)
            self._report_writer.write("\n")

    def reserve_memory_region(
            self, region, size, label=None, empty=False, reference=None):
        """
        Insert command to reserve a memory region.

        :param int region: The number of the region to reserve, from 0 to 15
        :param int size: The size to reserve for the region, in bytes
        :param label: An optional label for the region
        :type label: str or None
        :param bool empty: Specifies if the region will be left empty
        :param reference: A globally unique reference for this region
        :type reference: int or None
        :raise RegionInUseException: If the ``region`` was already reserved
        :raise ParameterOutOfBoundsException:
            If the ``region`` requested was out of the allowed range, or the
            ``size`` was too big to fit in SDRAM
        """
        if self._report_writer is not None:
            cmd_string = f"RESERVE memRegion={region:d} size={size:d}"
            if label is not None:
                cmd_string += f" label='{label}'"
            if empty:
                cmd_string += " UNFILLED"
            if reference is not None:
                cmd_string += f" REF {reference:d}"
            cmd_string += "\n"
            self._report_writer.write(cmd_string)

        if size % BYTES_PER_WORD != 0:
            size = size + (BYTES_PER_WORD - (size % BYTES_PER_WORD))

        self._ds_db.write_memory_region(
            self._core_id, region, size, reference, label)

    def reference_memory_region(self, region, ref, label=None):
        """
        Insert command to reference another memory region.

        :param int region: The number of the region to reserve, from 0 to 15
        :param int ref: The identifier of the region to reference
        :param label: An optional label for the region
        :type label: str or None
        :raise RegionInUseException: If the ``region`` was already reserved
        :raise ParameterOutOfBoundsException:
            If the ``region`` requested was out of the allowed range, or the
            ``size`` was too big to fit in SDRAM
        """
        if self._report_writer is not None:
            cmd_string = f"REFERENCE memRegion={region:d} ref={ref:d}"
            if label is not None:
                cmd_string += f" label='{label}'"
            cmd_string += "\n"
            self._report_writer.write(cmd_string)

        self._ds_db.write_reference(self._core_id, region, ref)

    def _typebounds(self, cmd, name, value, valuetype):
        """
        A simple bounds checker that uses the bounds from a type descriptor.
        """
        if valuetype not in DataType:
            raise UnknownTypeException(valuetype, cmd)
        if value < valuetype.min or value > valuetype.max:
            raise ParameterOutOfBoundsException(
                name, value, valuetype.min, valuetype.max, cmd)

    def create_cmd(self, data, data_type=DataType.UINT32):
        """
        Creates command to write a value to the current write pointer, causing
        the write pointer to move on by the number of bytes required to
        represent the data type. The data is passed as a parameter to this
        function.

        .. note::
            This does not actually insert the ``WRITE`` command in the spec;
            that is done by :py:meth:`write_cmd`.

        :param data: the data to write.
        :type data: int or float
        :param DataType data_type: the type to convert ``data`` to
        :return: ``cmd_word_list`` (binary data to be added to the binary data
            specification file), and ``cmd_string`` (string describing the
            command to be added to the report for the data specification file)
        :rtype: tuple(bytearray, str)
        :raise ParameterOutOfBoundsException:
            * If ``data_type`` is an integer type, and ``data`` has a
              fractional part
            * If ``data`` would overflow the data type
        :raise UnknownTypeException: If the data type is not known
        :raise InvalidSizeException: If the data size is invalid
        """
        raise NotImplementedError("create_cmd")

    def write_value(self, data, data_type=DataType.UINT32):
        """
        Insert command to write a value (once) to the current write pointer,
        causing the write pointer to move on by the number of bytes required
        to represent the data type. The data is passed as a parameter to this
        function

        .. note::
            This method used to have two extra parameters ``repeats`` and
            ``repeats_is_register``. They have been removed here. If you need
            them, use :meth:`write_repeated_value`

        :param data: the data to write as a float.
        :type data: int or float
        :param DataType data_type: the type to convert ``data`` to
        :raise ParameterOutOfBoundsException:
            * If ``data_type`` is an integer type, and ``data`` has a
              fractional part
            * If ``data`` would overflow the data type
        :raise UnknownTypeException: If the data type is not known
        :raise InvalidSizeException: If the data size is invalid
        :raise NoRegionSelectedException: If no region has been selected
        """
        self._typebounds("WRITE", "data", data, data_type)

        encoded = data_type.encode(data)
        if self._report_writer is not None:
            cmd_string = f"WRITE data={data}, dataType={data_type.name} " \
                         f"as {encoded}\n"
            self._report_writer.write(cmd_string)
        self._data += encoded
        self._data_debug += f"{data}:{data_type.name} "

    def write_array(self, array_values, data_type=DataType.UINT32):
        """
        Insert command to write an array, causing the write pointer
        to move on by (data type size * the array size), in bytes.

        :param array_values: An array of words to be written
        :type array_values: list(int) or list(float) or ~numpy.ndarray
        :param DataType data_type: Type of data contained in the array
        :raise NoRegionSelectedException: If no region has been selected
        """
        if data_type.numpy_typename is None:
            raise TypeMismatchException("WRITE_ARRAY")

        data = numpy.array(array_values, dtype=data_type.numpy_typename)
        size = data.size * data_type.size

        if size % 4 != 0:
            raise UnknownTypeLengthException(size, "WRITE_ARRAY")

        encoded = data.tostring()
        if self._report_writer is not None:
            cmd_string = f"WRITE_ARRAY {size // 4:d} elements\n"
            cmd_string += str(list(array_values))
            cmd_string += f"as {encoded}\n"
            self._report_writer.write(cmd_string)
        self._data += encoded
        self._data_debug += f"{array_values}:Array "

    def _end_region(self):
        if self._data is not None and len(self._data) > 0:
            self._ds_db.set_write_data(
                self._region_id, self._offset, self._data, self._data_debug)
        self._data = bytearray()
        self._data_debug = ""
        self._offset = 0

    def switch_write_focus(self, region):
        """
        Insert command to switch the region being written to.

        :param int region: The ID of the region to switch to, between 0 and 15
        :raise ParameterOutOfBoundsException:
            If the region identifier is not valid
        :raise NotAllocatedException: If the region has not been allocated
        :raise RegionUnfilledException:
            If the selected region should not be filled
        """
        self._end_region()

        if self._report_writer is not None:
            cmd_string = f"SWITCH_FOCUS memRegion = {region:d}\n"
            self._report_writer.write(cmd_string)

        self._region_id = self._ds_db.get_memory_region(
            self._core_id, region)

    def set_write_pointer(self, offset):
        """
        Insert command to set the position of the write pointer within the
        current region.

        :param int offset:
            The offset in the region to move the region pointer to
        :raise NoRegionSelectedException: If no region has been selected
        """
        self._end_region()
        self._offset = offset

    def end_specification(self, close_writer=True):
        """
        Insert a command to indicate that the specification has finished
        and finish writing.

        :param bool close_writer:
            Indicates whether to close the underlying writer(s)
        """
        self._end_region()
        self._ds_db = None
