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
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.exceptions import DataSpecException
from .data_specification_generator import DataSpecificationBase


class DataSpecificationReloader(DataSpecificationBase):
    """
    Used to reload the data specification data
    """

    __slots__ = []

    def __init__(self, x, y, p, ds_db, report_writer=None):
        super().__init__(x, y, p, None, ds_db, report_writer)

    @overrides(DataSpecificationBase.reserve_memory_region)
    def reserve_memory_region(
            self, region, size, label=None, reference=None):
        _, original_size = self._ds_db.get_memory_region(
            self._core_id, region)
        if original_size != size:
            raise DataSpecException(
                f"Size changed form original {original_size} to {size}")
        if reference is not None:
            raise NotImplementedError(
                "reference unexpected during reload")

    @overrides(DataSpecificationBase.reference_memory_region)
    def reference_memory_region(self, region, ref, label=None):
        raise NotImplementedError(
            "reference_memory_region unexpected during reload")

    def _end_write_block(self):
        if self._data is not None and len(self._data) > 0:

            x, y, pointer = self._ds_db.get_region_info(self._region_id)

            # Safety check if in debug mode
            self._check_write_block()

            FecDataView.write_memory(
                x, y, pointer + self._offset, self._data)

        self._data = bytearray()
        self._data_debug = ""
        self._offset = 0
