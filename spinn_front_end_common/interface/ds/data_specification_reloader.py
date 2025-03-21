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

from typing import Optional
from spinn_utilities.overrides import overrides
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.exceptions import DataSpecException
from .data_specification_generator import DataSpecificationBase


class DataSpecificationReloader(DataSpecificationBase):
    """
    Used to reload the data specification data
    """

    __slots__ = ()

    @overrides(DataSpecificationBase.reserve_memory_region)
    def reserve_memory_region(
            self, region: int, size: int, label: Optional[str] = None,
            reference: Optional[int] = None) -> None:
        original_size = self._ds_db.get_region_size(
            self._x, self._y, self._p, region)
        if original_size != size:
            raise DataSpecException(
                f"Size changed form original {original_size} to {size}")
        if reference is not None:
            raise NotImplementedError(
                "reference unexpected during reload")

    @overrides(DataSpecificationBase.reference_memory_region)
    def reference_memory_region(
            self, region: int, ref: int, label: Optional[str] = None) -> None:
        raise NotImplementedError(
            "reference_memory_region unexpected during reload")

    def _end_block(self) -> None:
        if self._region_num is None:
            raise DataSpecException("region number is unknown?!")

        pointer = self._ds_db.get_region_pointer(
            self._x, self._y, self._p, self._region_num)
        if pointer is None:
            raise DataSpecException("region pointer is unknown?!")

        self._check_write_block()

        assert self._content is not None
        FecDataView.write_memory(self._x, self._y, pointer, self._content)
