# Copyright (c) 2017 The University of Manchester
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

import logging
import os
import sqlite3
from typing import Dict, Iterable, List, Optional, Tuple, cast

import numpy

from spinn_utilities.log import FormatAdapter
from spinn_utilities.typing.coords import XYP

from spinnman.model.enums import ExecutableType
from spinnman.spalloc.spalloc_allocator import SpallocJobController
from spinnman.spalloc.spalloc_job import SpallocJob

from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinn_front_end_common.utilities.constants import (
    APP_PTR_TABLE_BYTE_SIZE)
from spinn_front_end_common.utilities.exceptions import DsDatabaseException
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB


_DDL_FILE = os.path.join(os.path.dirname(__file__), "dse.sql")
logger = FormatAdapter(logging.getLogger(__name__))

# Stop large numbers being written as blobs
sqlite3.register_adapter(numpy.int64, int)
sqlite3.register_adapter(numpy.int32, int)


class DsSqlliteDatabase(SQLiteDB):
    """
    A database for holding data specification details.
    """
    __slots__ = ["_init_file"]

    def __init__(self, database_file:  Optional[str] = None):
        """
        :param database_file:
            The name of a file that contains (or will contain) an SQLite
            database holding the data.
            If omitted the default location is used.
        """
        if database_file is None:
            database_file = FecDataView.get_ds_database_path()

        self._init_file = not os.path.exists(database_file)

        super().__init__(
            database_file, ddl_file=_DDL_FILE if self._init_file else None)

    def _context_entered(self) -> None:
        super()._context_entered()
        if self._init_file:
            self.__init_ethernets()
            self._init_file = False

    def __init_ethernets(self) -> None:
        """
        Set up the database contents from the machine.

        .. note:: Call of this method has to be delayed until inside the with
        """
        eth_chips = FecDataView.get_machine().ethernet_connected_chips
        self.cursor().executemany(
            """
            INSERT INTO ethernet(
                ethernet_x, ethernet_y, ip_address)
            VALUES(?, ?, ?)
            """, (
                (ethernet.x, ethernet.y, ethernet.ip_address)
                for ethernet in eth_chips))

    def set_core(self, x: int, y: int, p: int,
                 vertex: AbstractHasAssociatedBinary) -> None:
        """
        Creates a database record for the core with this x,y,z

        :param x: X coordinate of the core
        :param y: Y coordinate of the core
        :param p: Processor ID of the core
        :param vertex: Vertex to check if it is a system vertex.
            if missing this method will not create a new record
        :raises AttributeError:
            If the vertex is not an AbstractHasAssociatedBinary
        :raises KeyError:
            If there is no Chip as x, y
        :raises ~sqlite3.IntegrityError:
            If this combination of x, y, p has already been used
            Even if with the same vertex
        """
        self._set_chip(x, y)
        if vertex.get_binary_start_type() == ExecutableType.SYSTEM:
            is_system = 1
        else:
            is_system = 0
        self.cursor().execute(
            """
            INSERT INTO core(x, y, p, is_system)
            VALUES(?, ?, ?, ?)
            """, (x, y, p, is_system))

    def get_core_infos(self, is_system: bool) -> List[
            Tuple[int, int, int, int, int]]:
        """
        Gets a list of id, x, y, p, ethernet_x, ethernet_y for all cores
        according to is_system

        :param is_system: if True returns system cores
            otherwise application cores
        :return:
            (x, y, p, ethernet_x, ethernet_y)
            for each system or app core
        """
        core_infos: List[Tuple[int, int, int, int, int]] = []
        for row in self.cursor().execute(
                """
                SELECT x, y, p, ethernet_x, ethernet_y
                FROM core_view
                WHERE is_system = ?
                ORDER BY x, y, p
                 """, (is_system,)):
            core_infos.append(
                (row["x"], row["y"], row["p"],
                 row["ethernet_x"], row["ethernet_y"]))
        return core_infos

    def _set_chip(self, x: int, y: int) -> None:
        # skip if it already exists
        for _ in self.cursor().execute(
                """
                SELECT x
                FROM chip
                WHERE x = ? AND y = ?
                LIMIT 1
                """, (x, y)):
            return
        chip = FecDataView().get_chip_at(x, y)
        self.cursor().execute(
            """
            INSERT INTO chip(x, y, ethernet_x, ethernet_y) VALUES(?, ?, ?, ?)
            """, (x, y, chip.nearest_ethernet_x, chip.nearest_ethernet_y))

    def set_memory_region(
            self, x: int, y: int, p: int, region_num: int, size: int,
            reference: Optional[int], label: Optional[str]) -> int:
        """
        Writes the information to reserve a memory region into the database

        Typically called after a DS.reserve_memory_region call

        :param x: X coordinate of the core
        :param y: Y coordinate of the core
        :param p: Processor ID of the core t
        :param region_num: The number of the region to reserve
        :param size: The size to reserve for the region, in bytes
        :param label: An optional label for the region
        :param reference: A globally unique reference for this region
        :return:
        """
        self.cursor().execute(
            """
            INSERT INTO region(
                x, y, p, region_num, size, reference_num, region_label)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """, (x, y, p, region_num, size, reference, label))
        return self.lastrowid

    def get_region_size(self, x: int, y: int, p: int, region_num: int) -> int:
        """
        Gets the size for a region with this x, y, p and region

        :param x: X coordinate of the core
        :param y: Y coordinate of the core
        :param p: Processor ID of the core
        :param region_num: The region number
        :return: The size of the region, in bytes
        """
        for row in self.cursor().execute(
                """
                SELECT size
                FROM region
                WHERE x = ? AND y = ? AND p = ? AND region_num = ?
                LIMIT 1
                """, (x, y, p, region_num)):
            return row["size"]
        raise DsDatabaseException(f"Region {region_num} not set")

    def set_reference(self, x: int, y: int, p: int, region_num: int,
                      reference: int, ref_label: Optional[str]) -> None:
        """
        Writes a outgoing region_reference into the database

        :param x: X coordinate of the core
        :param y: Y coordinate of the core
        :param p: Processor ID of the core
        :param region_num: The region number
        :param reference: The number of the reference on this core
        :param ref_label: label for the referencing region
        """
        self.cursor().execute(
            """
            INSERT INTO reference(
                x, y, p, region_num, reference_num, ref_label)
            VALUES(?, ?, ?, ?, ?, ?)
            """, (x, y, p, region_num, reference, ref_label))

    def get_reference_pointers(self, x: int, y: int, p: int) -> Iterable[
            Tuple[int, int]]:
        """
        Yields the reference regions and where they point for this core

        This may yield nothing if there are no reference pointers or
        if the core is not known

        .. note::
            Do not use the database for anything else while iterating.

        :param x: X coordinate of the core
        :param y: Y coordinate of the core
        :param p: Processor ID of the core
        :return: Yields the referencing vertex region number and the pointer
        """
        for row in self.cursor().execute(
                """
                SELECT ref_region, pointer
                FROM linked_reference_view
                WHERE x = ? AND y = ? AND ref_p = ?
                """, (x, y, p)):
            yield row["ref_region"], row["pointer"]

    def get_unlinked_references(self) -> Iterable[
            Tuple[int, int, int, int, int, str]]:
        """
        Finds and yields info on unreferenced links

        If all is well this method yields nothing!

        .. note::
            Do not use the database for anything else while iterating.

        :return: x, y, p, region, reference, label for all unlinked references
        """
        for row in self.cursor().execute(
                """
                SELECT  x, y, ref_p, ref_region, reference_num,
                    COALESCE(ref_label, "") as ref_label
                FROM linked_reference_view
                WHERE act_region IS NULL
                 """):
            yield (row["x"], row["y"], row["ref_p"], row["ref_region"],
                   row["reference_num"], str(row["ref_label"], "utf8"))

    def get_double_region(self) -> Iterable[Tuple[int, int, int, int]]:
        """
        Finds and yields any region that was used in both region definition
            and a reference

         If all is well this method yields nothing!

        .. note::
            Do not use the database for anything else while iterating.

        :return: x, y, p, region
        """
        for row in self.cursor().execute(
                """
                SELECT x, y, p, region_num
                FROM pointer_content_view
                GROUP BY X, y, p, region_num
                HAVING count(*) != 1
                 """):
            yield (row["x"], row["y"], row["p"], row["region_num"])

    def set_region_content(
            self, x: int, y: int, p: int, region_num: int, content: bytes,
            content_debug: Optional[str]) -> None:
        """
        Sets the content for this region

        :param x: X coordinate of the core
        :param y: Y coordinate of the core
        :param p: Processor ID of the core
        :param region_num: The region number
        :param content: content to write
        :param content_debug: debug text
        :raises DsDatabaseException: If the region already has content
        """
        # check for previous content
        for row in self.cursor().execute(
                """
                SELECT content
                FROM region
                WHERE x = ? AND y = ? and p = ? and region_num = ?
                LIMIT 1
                """, (x, y, p, region_num)):
            if row["content"]:
                raise DsDatabaseException(
                    f"Illegal attempt to overwrite content for "
                    f"{x=} {y=} {p=} {region_num=}")

        self.cursor().execute(
            """
            UPDATE region
            SET content = ?, content_debug = ?
            WHERE x = ? AND y = ? and p = ? and region_num = ?
            """, (content, content_debug, x, y, p, region_num))
        if self.rowcount == 0:
            raise DsDatabaseException(
                f"No region {x=} {y=} {p=} {region_num=}")

    def get_region_pointer(
            self, x: int, y: int, p: int, region_num: int) -> Optional[int]:
        """
        Gets the pointer for this region as set during the original load

        returns None if the region is known but for some reason the pointer
        was not set

        :param x: X coordinate of the core
        :param y: Y coordinate of the core
        :param p: Processor ID of the core
        :param region_num: The Data Specification region number
        :return: The pointer set during the original load
        :raises DsDatabaseException: if the region is not known
        """
        for row in self.cursor().execute(
                """
                SELECT pointer
                FROM region
                WHERE x = ? AND y = ? AND p = ? AND region_num = ?
                LIMIT 1
                """, (x, y, p, region_num)):
            return row["pointer"]
        raise DsDatabaseException(f"No region {x=} {y=} {p=} {region_num=}")

    def get_region_sizes(self, x: int, y: int, p: int) -> Dict[int, int]:
        """
        Gets a dict of the regions and sizes reserved

        The returned dict will be empty if there are no regions reserved
        or if the core is not known.

        :param x: X coordinate of the core
        :param y: Y coordinate of the core
        :param p: Processor ID of the core
        :return: dict of region_num to size but only for regions with a size
        """
        regions: Dict[int, int] = dict()
        for row in self.cursor().execute(
                """
                SELECT region_num, size
                FROM region
                WHERE x = ? AND y = ? AND p = ?
                ORDER BY region_num
                """, (x, y, p)):
            regions[row["region_num"]] = row["size"]
        return regions

    def get_total_regions_size(self, x: int, y: int, p: int) -> int:
        """
        Gets the total size of the regions of this core

        Does not include the size of the pointer table

        Returns 0 even if the core is not known

        :param x: X coordinate of the core
        :param y: Y coordinate of the core
        :param p: Processor ID of the core
        :return: The size of the regions
            or 0 if there are no regions for this core
        """
        for row in self.cursor().execute(
                """
                SELECT COALESCE(sum(size), 0) as total
                FROM region
                WHERE x = ? AND y = ? AND p = ?
                LIMIT 1
                """, (x, y, p)):
            return row["total"]
        raise DsDatabaseException("Query failed unexpectedly")

    def set_start_address(
            self, x: int, y: int, p: int, start_address: int) -> None:
        """
        Sets the base address for a core and calculates pointers

        :param x: X coordinate of the core
        :param y: Y coordinate of the core
        :param p: Processor ID of the core
        :param start_address: The base address for the whole core
        :raises DsDatabaseException: if the region is not known
        """
        self.cursor().execute(
            """
            UPDATE core
            SET start_address = ?
            WHERE x = ? AND y = ? AND p = ?
            """, (start_address, x, y, p))
        if self.rowcount == 0:
            raise DsDatabaseException(
                f"No core {x=} {y=} {p=}")

    def get_start_address(self, x: int, y: int, p: int) -> int:
        """
        Gets the start_address for this core

        :param x: X coordinate of the core
        :param y: Y coordinate of the core
        :param p: Processor ID of the core
        :return: The base address for the whole core
        """
        for row in self.cursor().execute(
                """
                SELECT start_address
                FROM core
                WHERE x = ? AND y = ? and p = ?
                LIMIT 1
                """, (x, y, p)):
            return row["start_address"]
        raise DsDatabaseException(f"No core {x=} {y=} {p=}")

    def set_region_pointer(self, x: int, y: int, p: int, region_num: int,
                           pointer: int) -> None:
        """
        Sets the pointer to the start of the address for this x, y, p region.

        :param x:
        :param y:
        :param p:
        :param region_num:
        :param pointer:  start address
        """
        self.cursor().execute(
            """
            UPDATE region
            SET pointer = ?
            WHERE x = ? AND y = ? and p = ? and region_num = ?
            """, (pointer, x, y, p, region_num))
        if self.rowcount == 0:
            raise DsDatabaseException(
                f"No region {x=} {y=} {p=} {region_num=}")

    def get_region_pointers_and_content(
            self, x: int, y: int, p: int) -> Iterable[Tuple[
                int, int, Optional[bytes]]]:
        """
        Yields the number, pointers and content for each reserved region

        This includes regions with no content set where content will be None

        Will yield nothing if there are no regions reserved or if the core is
        not known

        :param x: X coordinate of the core
        :param y: Y coordinate of the core
        :param p: Processor ID of the core
        :return: number, pointer and (content or None)
        """
        for row in self.cursor().execute(
                """
                SELECT region_num, content, pointer
                FROM pointer_content_view
                WHERE x = ? AND y = ? AND p = ?
                ORDER BY region_num
                 """, (x, y, p)):
            if row["content"]:
                content = bytearray(row["content"])
            else:
                content = None
            yield row["region_num"], row["pointer"], content

    def get_regions_content(
            self, x: int, y: int, p: int) -> Iterable[Tuple[int, int, bytes]]:
        """
        Yields the number, pointers and content for each region

        This does not include regions with no content set

        Will yield nothing if there are no regions with content
        or if the core the is not known

        :param x: X coordinate of the core
        :param y: Y coordinate of the core
        :param p: Processor ID of the core
        :return: number, pointer and (content or None)
        """
        for row in self.cursor().execute(
                """
                SELECT region_num, content, pointer
                FROM region
                WHERE x = ? AND y = ? AND p = ? AND content IS NOT NULL
                ORDER BY region_num
                 """, (x, y, p)):
            yield row["region_num"], row["pointer"], bytearray(row["content"])

    def get_max_content_size(self, is_system: bool) -> int:
        """
        :param is_system: if True returns system cores
            otherwise application cores
        :returns: The size of the largest content.
        :raises DsDatabaseException:
        """
        for row in self.cursor().execute(
                """
                SELECT MAX(LENGTH(content)) AS size
                FROM region NATURAL JOIN CORE
                WHERE is_system = ?
                LIMIT 1
                 """, (is_system,)):
            the_max = row["Size"]
            if the_max is None:
                return 0
            return the_max
        raise DsDatabaseException("Max content size query")

    def get_content_sizes(self, is_system: bool) -> List[Tuple[int, int]]:
        """
        Returns the sizes of the content and the count of each size.

        Will return an empty list if there is no none Null content

        :param is_system: if True returns system cores
            otherwise application cores
        :returns: The sizes of the content and the count of each size
        """
        sizes: List[Tuple[int, int]] = []
        for row in self.cursor().execute(
                """
                SELECT LENGTH(content) AS size, COUNT(*) AS num
                FROM region NATURAL JOIN core
                WHERE is_system = ? AND content IS NOT NULL
                GROUP BY size
                ORDER BY size DESC
                """, (is_system,)):
            sizes.append((row["size"], row["num"]))
        return sizes

    def get_ds_cores(self) -> Iterable[XYP]:
        """
        Yields the x, y, p for the cores with possible Data Specifications

        Includes cores where DataSpecs started even if no regions reserved

        Yields nothing if there are no unknown cores

        .. note::
            Do not use the database for anything else while iterating.

        :return: Yields the (x, y, p)
        """
        for row in self.cursor().execute(
                """
                SELECT x, y, p FROM core
                """):
            yield (row["x"], row["y"], row["p"])

    def get_n_ds_cores(self) -> int:
        """
        Returns the number for cores there is a data specification saved for.

        Includes cores where DataSpecs started even if no regions reserved

        :raises DsDatabaseException:
        :returns: The number for cores with a data specification.
        """
        for row in self.cursor().execute(
                """
                SELECT COUNT(*) as count FROM core
                LIMIT 1
                """):
            return row["count"]
        raise DsDatabaseException("Count query failed")

    def get_memory_to_malloc(self, x: int, y: int, p: int) -> int:
        """
        Gets the expected number of bytes to be written

        :param x: core X coordinate
        :param y: core Y coordinate
        :param p: core processor ID
        :return: expected memory_written in bytes
        """
        to_malloc = APP_PTR_TABLE_BYTE_SIZE
        # try the fast way using regions
        for row in self.cursor().execute(
                """
                SELECT regions_size
                FROM region_size_view
                WHERE x = ? AND y = ? AND p = ?
                LIMIT 1
                """, (x, y, p)):
            to_malloc += row["regions_size"]
        return to_malloc

    def get_memory_to_write(self, x: int, y: int, p: int) -> int:
        """
        Gets the expected number of bytes to be written

        :param x: core X coordinate
        :param y: core Y coordinate
        :param p: core processor ID
        :return: expected memory_written in bytes
        """
        to_write = APP_PTR_TABLE_BYTE_SIZE
        # try the fast way using regions
        for row in self.cursor().execute(
                """
                SELECT contents_size
                FROM content_size_view
                WHERE x = ? AND y = ? AND p = ?
                LIMIT 1
                """, (x, y, p)):
            to_write += row["contents_size"]
        return to_write

    def get_info_for_cores(self) -> Iterable[Tuple[XYP, int, int, int]]:
        """
        Yields the (x, y, p) and write info for each core

        The sizes INCLUDE pointer table size

        Yields nothing if no cores known

        .. note::
            A DB transaction may be held while this iterator is processing.
            Reentrant use of this class is not supported.

        :return: Yields the (x, y, p), start_address, memory_used
            and memory_written
        """
        for row in self.cursor().execute(
                """
                SELECT x, y, p, start_address, to_write,malloc_size
                FROM core_summary_view
                """):
            yield ((row["x"], row["y"], row["p"]), row["start_address"],
                   row["malloc_size"], row["to_write"])

    def write_session_credentials_to_db(self) -> None:
        """
        Write Spalloc session credentials to the database, if in use.
        """
        if not FecDataView.has_allocation_controller():
            return
        mac = FecDataView.get_allocation_controller()
        if mac.proxying:
            # This is now assumed to be a SpallocJobController;
            # can't check that because of import circularity.
            job = cast(SpallocJobController, mac).job
            if isinstance(job, SpallocJob):
                config = job.get_session_credentials_for_db()
                self.cursor().executemany(
                    """
                    INSERT INTO proxy_configuration(kind, name, value)
                    VALUES(?, ?, ?)
                    """, [(k1, k2, v) for (k1, k2), v in config.items()])

    def set_info(self) -> None:
        """
        Sets the general information
        """
        # check for previous content
        machine = FecDataView().get_machine()
        self.cursor().execute(
            """
            INSERT INTO info(app_id, width, height)
            VALUES(?, ?, ?)
            """, (FecDataView.get_app_id(), machine.width, machine.height))
        if self.rowcount == 0:
            raise DsDatabaseException("Unable to set info")
