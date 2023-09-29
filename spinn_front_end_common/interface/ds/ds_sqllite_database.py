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
import numpy
import os
import sqlite3
from spinn_utilities.log import FormatAdapter
from spinnman.model.enums import ExecutableType
from spinnman.spalloc.spalloc_job import SpallocJob
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.constants import (
    APP_PTR_TABLE_BYTE_SIZE)
from spinn_front_end_common.utilities.exceptions import DsDatabaseException
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB

_DDL_FILE = os.path.join(os.path.dirname(__file__), "dse.sql")
logger = FormatAdapter(logging.getLogger(__name__))

# Stop large numbers being written as blobs
# pylint: disable=unnecessary-lambda
sqlite3.register_adapter(numpy.int64, lambda val: int(val))
sqlite3.register_adapter(numpy.int32, lambda val: int(val))


class DsSqlliteDatabase(SQLiteDB):
    """
    A database for holding data specification details.
    """
    __slots__ = ["_init_file"]

    def __init__(self, database_file=None):
        if database_file is None:
            database_file = FecDataView.get_ds_database_path()

        self._init_file = not os.path.exists(database_file)

        super().__init__(
            database_file, ddl_file=_DDL_FILE if self._init_file else None)

    def _context_entered(self):
        super()._context_entered()
        if self._init_file:
            self.__init_ethernets()
            self._init_file = False

    def __init_ethernets(self):
        """
        Set up the database contents from the machine.
        """
        eth_chips = FecDataView.get_machine().ethernet_connected_chips
        self.executemany(
            """
            INSERT INTO ethernet(
                ethernet_x, ethernet_y, ip_address)
            VALUES(?, ?, ?)
            """, (
                (ethernet.x, ethernet.y, ethernet.ip_address)
                for ethernet in eth_chips))

    def set_core(self, x, y, p, vertex):
        """
        Creates a database record for the core with this x,y,z

        :param int x: X coordinate of the core
        :param int y: Y coordinate of the core
        :param int p: Processor ID of the core
        :param vertex: Vertex to check if it is a system vertex.
            if missing this method will not create a new record
        :type vertex:
            ~spinn_front_end_common.abstract_models.AbstractHasAssociatedBinary
        :rtype: int
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
        self.execute(
            """
            INSERT INTO core(x, y, p, is_system)
            VALUES(?, ?, ?, ?)
            """, (x, y, p, is_system))

    def get_core_infos(self, is_system):
        """
        Gets a list of id, x, y, p, ethernet_x, ethernet_y for all cores
        according to is_system

        :param bool is_system: if True returns systenm cores
            otherwise application cores
        :return:
            list(database_id, x, y, p, ethernet_x, ethernet_y)
            for each system or app core
        :rtype: list(int, int, int, int, int, int)
        """
        core_infos = []
        for row in self.execute(
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

    def _set_chip(self, x, y):
        """
        :param int x:
        :param int y:
        """
        # skip if it already exists
        for _ in self.execute(
                """
                SELECT x
                FROM chip
                WHERE x = ? AND y = ?
                LIMIT 1
                """, (x, y)):
            return
        chip = FecDataView().get_chip_at(x, y)
        self.execute(
            """
            INSERT INTO chip(x, y, ethernet_x, ethernet_y) VALUES(?, ?, ?, ?)
            """, (x, y, chip.nearest_ethernet_x, chip.nearest_ethernet_y))

    def set_memory_region(
            self, x, y, p, region_num, size, reference, label):
        """
        Writes the information to reserve a memory region into the database

        Typically called after a DS.reserve_memory_region call

        :param int x: X coordinate of the core
        :param int y: Y coordinate of the core
        :param int p: Processor ID of the core t
        :param int region: The number of the region to reserve
        :param int size: The size to reserve for the region, in bytes
        :param label: An optional label for the region
        :type label: str or None
        :param reference: A globally unique reference for this region
        :type reference: int or None
        :param label:
        :return:
        """
        self.execute(
            """
            INSERT INTO region(
                x, y, p, region_num, size, reference_num, region_label)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """, (x, y, p, region_num, size, reference, label))
        return self.lastrowid

    def get_region_size(self, x, y, p, region_num):
        """
        Gets the size for a region with this x, y, p and region

        :param int x: X coordinate of the core
        :param int y: Y coordinate of the core
        :param int p: Processor ID of the core
        :param int region_num: The region number
        :return: The database id for this region and the size in bytes
        :rtype: int
        """
        for row in self.execute(
                """
                SELECT size
                FROM region
                WHERE x = ? AND y = ? AND p = ? AND region_num = ?
                LIMIT 1
                """, (x, y, p, region_num)):
            return row["size"]
        raise DsDatabaseException(f"Region {region_num} not set")

    def set_reference(self, x, y, p, region_num, reference, ref_label):
        """
        Writes a outgoing region_reference into the database

        :param int x: X coordinate of the core
        :param int y: Y coordinate of the core
        :param int p: Processor ID of the core
        :param int region_num: The region number
        :param int reference: The number of the reference on this core
        :param ref_label: label for the referencing region
        :type ref_label: str or None
        """
        self.execute(
            """
            INSERT INTO reference(
                x, y, p, region_num, reference_num, ref_label)
            VALUES(?, ?, ?, ?, ?, ?)
            """, (x, y, p, region_num, reference, ref_label))
        assert (self.rowcount == 1)

    def get_reference_pointers(self, x, y, p):
        """
        Yields the reference regions and where they point for this core

        This may yield nothing if there are no reference pointers or
        if the core is not known

        .. note::
            Do not use the database for anything else while iterating.

        :param int x: X coordinate of the core
        :param int y: Y coordinate of the core
        :param int p: Processor ID of the core
        :return: Yields the referencing vertex region number and the pointer
        :rtype: iterable(tuple(int,int))
        """
        for row in self.execute(
                """
                SELECT ref_region, pointer
                FROM linked_reference_view
                WHERE x = ? AND y = ? AND ref_p = ?
                """, (x, y, p)):
            yield row["ref_region"], row["pointer"]

    def get_unlinked_references(self):
        """
        Finds and yields info on unreferenced links

        If all is well this method yields nothing!

        .. note::
            Do not use the database for anything else while iterating.

        :return: x, y, p, region, reference, label for all unlinked references
        :rtype: iterable(tuple(int, int, int, int, int, str))
        """
        for row in self.execute(
                """
                SELECT  x, y, ref_p, ref_region, reference_num,
                    COALESCE(ref_label, "") as ref_label
                FROM linked_reference_view
                WHERE act_region IS NULL
                 """):
            yield (row["x"], row["y"], row["ref_p"], row["ref_region"],
                   row["reference_num"], str(row["ref_label"], "utf8"))

    def get_double_region(self):
        """
        Finds and yields any region that was used in both region definition
            and a reference

         If all is well this method yields nothing!

        .. note::
            Do not use the database for anything else while iterating.

        :return: x, y, p
        :rtype: iterable(tuple(int, int, int))
        """
        for row in self.execute(
                """
                SELECT x, y, p, region_num
                FROM pointer_content_view
                GROUP BY X, y, p, region_num
                HAVING count(*) != 1
                 """):
            yield (row["x"], row["y"], row["p"], row["region_num"])

    def set_region_content(self, x, y, p, region_num, content, content_debug):
        """
        Sets the content for this region

        :param int x: X coordinate of the core
        :param int y: Y coordinate of the core
        :param int p: Processor ID of the core
        :param int region_num: The region number
        :param bytearray content: content to write
        :param content_debug: debug text
        :type content_debug: str or None
        :raises DsDatabaseException: If the region already has content
        """
        # check for previous content
        for row in self.execute(
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

        self.execute(
            """
            UPDATE region
            SET content = ?, content_debug = ?
            WHERE x = ? AND y = ? and p = ? and region_num = ?
            """, (content, content_debug, x, y, p, region_num))
        if self.rowcount == 0:
            raise DsDatabaseException(
                f"No region {x=} {y=} {p=} {region_num=}")

    def get_region_pointer(self, x, y, p, region_num):
        """
        Gets the pointer for this region as set during the original load

        returns None if the region is known but for some reason the pointer
        was not set

        :param int x: X coordinate of the core
        :param int y: Y coordinate of the core
        :param int p: Processor ID of the core
        :param int region_num: The DS region number
        :return: The pointer set during the original load
        :rtype: int or None
        :raises DsDatabaseException: if the region is not known
        """
        for row in self.execute(
                """
                SELECT pointer
                FROM region
                WHERE x = ? AND y = ? AND p = ? AND region_num = ?
                LIMIT 1
                """, (x, y, p, region_num)):
            return row["pointer"]
        raise DsDatabaseException(f"No region {x=} {y=} {p=} {region_num=}")

    def get_region_sizes(self, x, y, p):
        """
        Gets a dict of the regions and sizes reserved

        The returned dict will be empty if there are no regions reserved
        or if the core is not known.

        :param int x: X coordinate of the core
        :param int y: Y coordinate of the core
        :param int p: Processor ID of the core
        :return: dict of region_num to size but only for regions with a size
        :rtype: dict(int, int)
        """
        regions = dict()
        for row in self.execute(
                """
                SELECT region_num, size
                FROM region
                WHERE x = ? AND y = ? AND p = ?
                ORDER BY region_num
                """, (x, y, p)):
            regions[row["region_num"]] = row["size"]
        return regions

    def get_total_regions_size(self, x, y, p):
        """
        Gets the total size of the regions of this core

        Does not include the size of the pointer table

        Returns 0 even if the core is not known

        :param int x: X coordinate of the core
        :param int y: Y coordinate of the core
        :param int p: Processor ID of the core
        :return: The size of the regions
            or 0 if there are no regions for this core
        :rtype: int
        """
        for row in self.execute(
            """
                SELECT COALESCE(sum(size), 0) as total
                FROM region
                WHERE x = ? AND y = ? AND p = ?
                LIMIT 1
                """, (x, y, p)):
            return row["total"]
        raise DsDatabaseException("Query failed unexpectedly")

    def set_start_address(self, x, y, p, start_address):
        """
        Sets the base address for a core and calculates pointers

        :param int x: X coordinate of the core
        :param int y: Y coordinate of the core
        :param int p: Processor ID of the core
        :param int start_address: The base address for the whole core
        :return: The expected size of the malloced_area
        :rtype: int
        :raises DsDatabaseException: if the region is not known
        """
        self.execute(
            """
            UPDATE core
            SET start_address = ?
            WHERE x = ? AND y = ? AND p = ?
            """, (start_address, x, y, p))
        if self.rowcount == 0:
            raise DsDatabaseException(
                f"No core {x=} {y=} {p=}")

    def get_start_address(self, x, y, p):
        """
        Gets the start_address for this core

        :param int x: X coordinate of the core
        :param int y: Y coordinate of the core
        :param int p: Processor ID of the core
        :return: The base address for the whole core
        :rtype: int
        """
        for row in self.execute(
                """
                SELECT start_address
                FROM core
                WHERE x = ? AND y = ? and p = ?
                LIMIT 1
                """, (x, y, p)):
            return row["start_address"]
        raise DsDatabaseException(f"No core {x=} {y=} {p=}")

    def set_region_pointer(self, x, y, p, region_num, pointer):
        self.execute(
            """
            UPDATE region
            SET pointer = ?
            WHERE x = ? AND y = ? and p = ? and region_num = ?
            """, (pointer, x, y, p, region_num))
        if self.rowcount == 0:
            raise DsDatabaseException(
                f"No region {x=} {y=} {p=} {region_num=}")

    def get_region_pointers_and_content(self, x, y, p):
        """
        Yields the number, pointers and content for each reserved region

        This includes regions with no content set where content will be None

        Will yield nothing if there are no regions reserved or if the core if
        not known

        :param int x: X coordinate of the core
        :param int y: Y coordinate of the core
        :param int p: Processor ID of the core
        :return: number, pointer and (content or None)
        :rtype: iterable(tuple(int, int, bytearray or None))
        """
        for row in self.execute(
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

    def get_ds_cores(self):
        """
        Yields the x, y, p for the cores with possible Data Specifications

        Includes cores where DataSpecs started even if no regions reserved

        Yields nothing if there are no unknown cores

        .. note::
            Do not use the database for anything else while iterating.

        :return: Yields the (x, y, p)
        :rtype: iterable(tuple(int,int,int))
        """
        for row in self.execute(
                """
                SELECT x, y, p FROM core
                """):
            yield (row["x"], row["y"], row["p"])

    def get_n_ds_cores(self):
        """
        Returns the number for cores there is a data specification saved for.

        Includes cores where DataSpecs started even if no regions reserved

        :rtype: int
        :raises DsDatabaseException:
        """
        for row in self.execute(
                """
                SELECT COUNT(*) as count FROM core
                LIMIT 1
                """):
            return row["count"]
        raise DsDatabaseException("Count query failed")

    def get_memory_to_malloc(self, x, y, p):
        """
        Gets the expected number of bytes to be written

        :param int x: core X coordinate
        :param int y: core Y coordinate
        :param int p: core processor ID
        :return: expected memory_written in bytes
        :rtype: int
        """
        to_malloc = APP_PTR_TABLE_BYTE_SIZE
        # try the fast way using regions
        for row in self.execute(
                """
                SELECT regions_size
                FROM region_size_view
                WHERE x = ? AND y = ? AND p = ?
                LIMIT 1
                """, (x, y, p)):
            to_malloc += row["regions_size"]
        return to_malloc

    def get_memory_to_write(self, x, y, p):
        """
        Gets the expected number of bytes to be written

        :param int x: core X coordinate
        :param int y: core Y coordinate
        :param int p: core processor ID
        :return: expected memory_written in bytes
        :rtype: int
        """
        to_write = APP_PTR_TABLE_BYTE_SIZE
        # try the fast way using regions
        for row in self.execute(
                """
                SELECT contents_size
                FROM content_size_view
                WHERE x = ? AND y = ? AND p = ?
                LIMIT 1
                """, (x, y, p)):
            to_write += row["contents_size"]
        return to_write

    def get_info_for_cores(self):
        """
        Yields the (x, y, p) and write info for each core

        The sizes INCLUDE pointer table size

        Yields nothing if no cores known

        .. note::
            A DB transaction may be held while this iterator is processing.
            Reentrant use of this class is not supported.

        :return: Yields the (x, y, p), start_address, memory_used
            and memory_written
        :rtype: iterable(tuple(tuple(int, int, int), int, int, int))
        """
        for row in self.execute(
                """
                SELECT x, y, p, start_address, to_write,malloc_size
                FROM core_summary_view
                """):
            yield ((row["x"], row["y"], row["p"]), row["start_address"],
                   row["malloc_size"], row["to_write"])

    def write_session_credentials_to_db(self):
        """
        Write Spalloc session credentials to the database, if in use.
        """
        # pylint: disable=protected-access
        if not FecDataView.has_allocation_controller():
            return
        mac = FecDataView.get_allocation_controller()
        if mac.proxying:
            # This is now assumed to be a SpallocJobController;
            # can't check that because of import circularity.
            job = mac._job
            if isinstance(job, SpallocJob):
                config = job.get_session_credentials_for_db()
                self.executemany("""
                    INSERT INTO proxy_configuration(kind, name, value)
                    VALUES(?, ?, ?)
                    """, [(k1, k2, v) for (k1, k2), v in config.items()])

    def set_app_id(self):
        """
        Sets the app id

        """
        # check for previous content
        self.execute(
            """
            INSERT INTO app_id(app_id)
            VALUES(?)
            """, (FecDataView.get_app_id(), ))
        if self.rowcount == 0:
            raise DsDatabaseException("Unable to set app id")
