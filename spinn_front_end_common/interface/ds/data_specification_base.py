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
from spinn_utilities.abstract_base import AbstractBase, abstractmethod
from data_specification.enums.data_type import DataType
from spinn_front_end_common.utilities.exceptions import DataSpecException
BYTES_PER_WORD = 4


class DataSpecificationBase(object, metaclass=AbstractBase):
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
        "_region_num",
        "_size"
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
        self._region_num = None
        self._size = None

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

    @abstractmethod
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

    @abstractmethod
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
        self._end_write_block()

        if self._report_writer is not None:
            cmd_string = f"SWITCH_FOCUS memRegion = {region:d}\n"
            self._report_writer.write(cmd_string)

        self._region_id, self._size = self._ds_db.get_memory_region(
            self._core_id, region)
        self._region_num = region
        if self._size <= 0:
            raise DataSpecException(f"No size set for region {region}")

    def create_cmd(self, data, data_type=DataType.UINT32):
        """
        Creates command to write a value to the current write pointer, causing
        the write pointer to move on by the number of bytes required to
        represent the data type. The data is passed as a parameter to this
        function.

        :raise NotImplementedError:
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
        :raise ValueError: If the data size is invalid
        :raise NoRegionSelectedException: If no region has been selected
        """
        data_type.check_value(data)

        as_bytes = data_type.as_bytes(data)
        if self._report_writer is not None:
            cmd_string = f"WRITE data={data}, dataType={data_type.name} " \
                         f"as {as_bytes}\n"
            self._report_writer.write(cmd_string)
        if len(as_bytes) > data_type.size:
            self._report_writer.flush()
            raise ValueError(
                f"{data}:{data_type.name} as bytes was {as_bytes} "
                f"when only {data_type.size} bytes expected")
        if len(self._data) % 4 != 0:  # check we are at a word boundary
            if len(data) % data_type.size != 0:
                raise NotImplementedError(
                    f"After {len(self._data)} bytes have been written "
                    f" unable to add data of type {data_type}"
                    f" without padding")

        self._data += as_bytes
        self._data_debug += f"{data}:{data_type.name} "

    def write_array(self, array_values, data_type=DataType.UINT32):
        """
        Insert command to write an array, causing the write pointer
        to move on by (data type size * the array size), in bytes.

        :param array_values: An array of words to be written
        :type array_values: list(int) or list(float) or ~numpy.ndarray
        :param DataType data_type: Type of data contained in the array
        """
        data = numpy.array(array_values, dtype=data_type.numpy_typename)

        encoded = data.tobytes()

        if self._report_writer is not None:
            cmd_string = f"WRITE_ARRAY {len(array_values)} elements in " \
                         f"{len(encoded)} bytes\n"
            if len(array_values) < 100:
                cmd_string += str(list(array_values))
                cmd_string += f"as {encoded}\n"
            self._report_writer.write(cmd_string)

        if len(self._data) % 4 != 0:  # check we are at a word boundary
            raise NotImplementedError(
                f"After {len(self._data)} bytes have been written "
                f"which is not a multiple of 4"
                f" write_array is not supported")
        if len(encoded) % 4 != 0:  # check we are at a word boundary
            raise NotImplementedError(
                f"Unexpected data (as bytes) length of {len(encoded)}")

        self._data += encoded
        self._data_debug += f"{array_values}:Array "

    def set_write_pointer(self, offset):
        """
        Insert command to set the position of the write pointer within the
        current region.

        :param int offset:
            The offset in the region to move the region pointer to
        :raise NoRegionSelectedException: If no region has been selected
        """
        self._end_write_block()
        if offset % 4 != 0:
            raise NotImplementedError(
                f"Unexpected offset of {offset} which is not a multiple of 4")
        self._offset = offset

    def _check_write_block(self):
        length = len(self._data)

        if self._report_writer is not None:
            cmd_string = f"loading {length} bytes " \
                         f"into region {self._region_id} " \
                         f"of size {self._size}\n"
            self._report_writer.write(cmd_string)

        if self._size < length:
            raise DataSpecException(
                f"Region size is {self._size} so unable to write {length} bytes")
        if self._size - self._offset < length:
            raise DataSpecException(
                f"Region size is {self._size} Offset is {self._offset} "
                f"so unable to write {length} bytes")
        if length % 4 != 0:
            raise NotImplementedError(
                "Unable to write {length} bytes as not a multiple of 4")

    @abstractmethod
    def _end_write_block(self):
        """
        Write data to the database and clears block

        """

    def end_specification(self):
        """
        Insert a command to indicate that the specification has finished
        and finish writing.

        :param bool close_writer:
            Indicates whether to close the underlying writer(s)
        """
        self._end_write_block()
