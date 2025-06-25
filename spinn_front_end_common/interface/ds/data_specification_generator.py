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

from typing import Optional, TextIO, Union, cast
from spinn_utilities.overrides import overrides
from spinn_front_end_common.utilities.constants import BYTES_PER_WORD
from spinn_front_end_common.utilities.exceptions import DataSpecException
from spinn_front_end_common.abstract_models import (
    AbstractGeneratesDataSpecification,
    AbstractRewritesDataSpecification, AbstractHasAssociatedBinary)
from .data_specification_base import DataSpecificationBase
from .ds_sqllite_database import DsSqlliteDatabase


class DataSpecificationGenerator(DataSpecificationBase):
    """
    Used to generate the data specification data in the database
    """

    __slots__ = ()

    def __init__(
            self, x: int, y: int, p: int,
            vertex: Union[
                AbstractGeneratesDataSpecification,
                AbstractRewritesDataSpecification],
            ds_db: DsSqlliteDatabase, report_writer: Optional[TextIO] = None):
        """
        :param x:
        :param y:
        :param p:
        :param vertex:
            The vertex being written.
        :param report_writer:
            Determines if a text version of the specification is to be
            written and, if so, where. No report is written if this is `None`.
        :raises DsDatabaseException: If this core is not known
            and no vertex supplied (during reload)
        :raises AttributeError:
            If the vertex is not an AbstractHasAssociatedBinary
        :raises KeyError:
            If there is no Chip as x, y
        :raises ~sqlite3.IntegrityError:
            If this combination of x, y, p has already been used
            Even if with the same vertex
        """
        super().__init__(x, y, p, ds_db, report_writer)
        ds_db.set_core(x, y, p, cast(AbstractHasAssociatedBinary, vertex))

    @overrides(DataSpecificationBase.reserve_memory_region)
    def reserve_memory_region(
            self, region: int, size: int, label: Optional[str] = None,
            reference: Optional[int] = None) -> None:
        self._report("RESERVE memRegion=", region, " size=", size,
                     (f" label='{label}'" if label else None),
                     (f" REF {reference}" if reference is not None else None))

        # Round up the size
        if size % BYTES_PER_WORD != 0:
            size = size + (BYTES_PER_WORD - (size % BYTES_PER_WORD))

        self._ds_db.set_memory_region(
            self._x, self._y, self._p, region, size, reference, label)

    @overrides(DataSpecificationBase.reference_memory_region)
    def reference_memory_region(
            self, region: int, ref: int, label: Optional[str] = None) -> None:
        self._report("REFERENCE memRegion=", region, " ref=", ref,
                     (f" label='{label}'" if label else None))

        self._ds_db.set_reference(
            self._x, self._y, self._p, region, ref, label)

    def _end_block(self) -> None:
        # Safety check if in debug mode
        self._check_write_block()
        assert self._content is not None
        if self._region_num is None:
            raise DataSpecException("region number is unknown?!")

        self._ds_db.set_region_content(
            self._x, self._y, self._p, self._region_num,
            self._content, self._content_debug)
