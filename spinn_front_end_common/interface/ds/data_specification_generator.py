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
        ds_db.set_core(x, y, p, vertex)

    @overrides(DataSpecificationBase.reserve_memory_region)
    def reserve_memory_region(
            self, region, size, label=None, reference=None):
        if self._report_writer is not None:
            cmd_string = f"RESERVE memRegion={region:d} size={size:d}"
            if label is not None:
                cmd_string += f" label='{label}'"
            if reference is not None:
                cmd_string += f" REF {reference:d}"
            cmd_string += "\n"
            self._report_writer.write(cmd_string)

        if size % BYTES_PER_WORD != 0:
            size = size + (BYTES_PER_WORD - (size % BYTES_PER_WORD))

        self._ds_db.set_memory_region(
            self._x, self._y, self._p, region, size, reference, label)

    @overrides(DataSpecificationBase.reference_memory_region)
    def reference_memory_region(self, region, ref, label=None):
        if self._report_writer is not None:
            cmd_string = f"REFERENCE memRegion={region:d} ref={ref:d}"
            if label is not None:
                cmd_string += f" label='{label}'"
            cmd_string += "\n"
            self._report_writer.write(cmd_string)

        self._ds_db.set_reference(
            self._x, self._y, self._p, region, ref, label)

    def _end_write_block(self):
        if self._content is not None and len(self._content) > 0:

            # Safety check if in debug mode
            self._check_write_block()

            self._ds_db.set_region_content(
                self._x, self._y, self._p, self._region_num,
                self._content, self._content_debug)

        self._content = bytearray()
        self._content_debug = ""
