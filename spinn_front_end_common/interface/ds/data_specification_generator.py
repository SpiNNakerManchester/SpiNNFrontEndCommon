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

from spinn_utilities.overrides import overrides
from spinn_front_end_common.utilities.constants import BYTES_PER_WORD
from .data_specification_base import DataSpecificationBase


class DataSpecificationGenerator(DataSpecificationBase):
    """
    Used to generate the data specification data in the database
    """

    __slots__ = []

    @overrides(DataSpecificationBase.reserve_memory_region)
    def reserve_memory_region(
            self, region, size, label=None, empty=False, reference=None):
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

    @overrides(DataSpecificationBase.reference_memory_region)
    def reference_memory_region(self, region, ref, label=None):
        if self._report_writer is not None:
            cmd_string = f"REFERENCE memRegion={region:d} ref={ref:d}"
            if label is not None:
                cmd_string += f" label='{label}'"
            cmd_string += "\n"
            self._report_writer.write(cmd_string)

        self._ds_db.write_reference(self._core_id, region, ref)

    def _end_write_block(self):
        if self._data is not None and len(self._data) > 0:

            # Safety check if in debug mode
            self._check_write_block()

            self._ds_db.set_write_data(
                self._region_id, self._offset, self._data, self._data_debug)

        self._data = bytearray()
        self._data_debug = ""
        self._offset = 0
