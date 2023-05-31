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
    __slots__ = []

    def __init__(self, init_file=None):
        """
        :param bool init_file:
            Whether to initialise the DB from our DDL file. If not specified,
            this is guessed from whether we can read the file.
        """
        database_file = self.default_database_file()

        if init_file is None:
            init_file = not os.path.exists(database_file)

        super().__init__(
            database_file, ddl_file=_DDL_FILE if init_file else None)
        if init_file:
            self.__init_ethernets()

    @classmethod
    def default_database_file(cls):
        """
        Gets the path to the default/ current database file

        :rtype: str
        :return: Path where the database is or should be writen
        """
        return os.path.join(FecDataView.get_run_dir_path(),
                            f"ds{FecDataView.get_reset_str()}.sqlite3")

    def __init_ethernets(self):
        """
        Set up the database contents from the machine.
        """
        eth_chips = FecDataView.get_machine().ethernet_connected_chips
        with self.transaction() as cursor:
            cursor.executemany(
                """
                INSERT INTO ethernet(
                    ethernet_x, ethernet_y, ip_address)
                VALUES(?, ?, ?)
                """, (
                    (ethernet.x, ethernet.y, ethernet.ip_address)
                    for ethernet in eth_chips))

    def set_core_id(self, x, y, p, vertex):
        """
        Creates a database record for the core with this x,y,z

        :param int x:
            X coordinate of the core that `spec_bytes` applies to
        :param int y:
            Y coordinate of the core that `spec_bytes` applies to
        :param int p: Processor ID of the core that `spec_bytes` applies to
        :vertex:
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
        with self.transaction() as cursor:
            chip_id = self._get_chip_id(cursor, x, y)
            if vertex.get_binary_start_type() == ExecutableType.SYSTEM:
                is_system = 1
            else:
                is_system = 0
            cursor.execute(
                """
                INSERT INTO core(chip_id, processor, is_system)
                VALUES(?, ?, ?)
                """, (chip_id, p, is_system))
            return cursor.lastrowid

    def get_core_id(self, x, y, p):
        """
        Gets the database core_id for the core with this x,y,z

        :param int x:
            X coordinate of the core that `spec_bytes` applies to
        :param int y:
            Y coordinate of the core that `spec_bytes` applies to
        :param int p: Processor ID of the core that `spec_bytes` applies to
        :rtype: int
        :raises DsDatabaseException:
            If there is no core, x, y, p in the database
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT core_id
                    FROM core_view
                    WHERE x = ? AND y = ? AND processor = ?
                    LIMIT 1
                    """, (x, y, p)):
                return row["core_id"]
        raise DsDatabaseException(f"No Core {x=} {y=} {p=}")

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
        with self.transaction() as cursor:
            core_infos = []
            for row in cursor.execute(
                    """
                    SELECT core_id, x, y, processor, ethernet_x, ethernet_y
                    FROM core_view
                    WHERE is_system = ?
                    ORDER BY core_id
                     """, (is_system,)):
                core_infos.append(
                    (row["core_id"], row["x"], row["y"], row["processor"],
                     row["ethernet_x"], row["ethernet_y"]))
        return core_infos

    def _get_chip_id(self, cursor, x, y):
        """
        :param ~sqlite3.Cursor cursor:
        :param int x:
        :param int y:
        :rtype: int
        """
        for row in cursor.execute(
                """
                SELECT chip_id FROM chip
                WHERE x = ? AND y = ?
                LIMIT 1
                """, (x, y)):
            return row["chip_id"]
        chip = FecDataView().get_chip_at(x, y)
        cursor.execute(
            """
            INSERT INTO chip(x, y, ethernet_x, ethernet_y) VALUES(?, ?, ?, ?)
            """, (x, y, chip.nearest_ethernet_x, chip.nearest_ethernet_y))
        return cursor.lastrowid

    def set_memory_region(
            self, core_id, region_num, size, reference, label):
        """
        Writes the information to reserve a memory region into the database

        Typically called after a DS.reserve_memory_region call

        :param int core_id: The database id for the core to reserve on
        :param int region: The DS number of the region to reserve
        :param int size: The size to reserve for the region, in bytes
        :param label: An optional label for the region
        :type label: str or None
        :param reference: A globally unique reference for this region
        :type reference: int or None
        :param label:
        :return:
        """
        with self.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO region(
                    core_id, region_num, size, reference_num, region_label)
                VALUES(?, ?, ?, ?, ?)
                """, (core_id, region_num, size, reference, label))
            return cursor.lastrowid

    def get_region_id_and_size(self, core_id, region_num):
        """
        Gets the database id and size for a region with this core_id

        :param int core_id: The id the database has for this core
        :param region_num: The DS region number
        :return: The database id for this region and the size in bytes
        :rtype: int, int
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT region_id, size FROM region
                    WHERE core_id = ? AND region_num = ?
                    LIMIT 1
                    """, (core_id, region_num)):
                return row["region_id"], row["size"]
        raise DsDatabaseException(f"Region {region_num} not set")

    def set_reference(self, core_id, region_num, reference, ref_label):
        """
        Writes a outgoing region_reference into the database

        :param int core_id: The id the database has for this core
        :param region_num: The DS region number
        :param int reference: DS number of the reference on this core
        :param ref_label: label for the refrencing region
        :type ref_label: str or None
        """
        with self.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO reference(
                    core_id, region_num, reference_num, ref_label)
                VALUES(?, ?, ?, ?)
                """, (core_id, region_num, reference, ref_label))

    def get_reference_pointers(self, core_id):
        """
        Yeilds the reference regions and where they point for this core

        :param int core_id: The id the database has for this core
        :return: Yields the refercing vertext region number and the pointer
        :rtype: iterable(tuple(int,int))
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT ref_region, pointer
                    FROM linked_reverence_view
                    WHERE ref_core_id = ?
                    """, (core_id,)):
                yield row["ref_region"], row["pointer"]

    def get_unlinked_references(self):
        """
        Finds and yeilds info on unreferenced links

        If all is well this method yields nothing!

        :return: x, y, p, region, reference, label for all unlinked references
        :rtype: iterable(tuple(int, int, int, int, int, str))
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT  x, y, ref_p, ref_region, reference_num, ref_label
                    FROM linked_reverence_view
                    WHERE act_region IS NULL
                     """):
                yield (row["x"], row["y"], row["ref_p"], row["ref_region"],
                       row["reference_num"], str(row["ref_label"], "utf8"))


    def set_write_data(self, region_id, offset, write_data, data_debug):
        with self.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO write(
                    region_id, offset, write_data, data_debug)
                VALUES(?, ?, ?, ?)
                """, (region_id, offset, write_data, data_debug))
            return cursor.lastrowid

    def get_write_data(self, region_id):
        data = None
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT offset, write_data
                    FROM write
                    WHERE region_id = ?
                    ORDER BY offset
                    """, (region_id,)):
                if data is None:
                    data = bytearray()
                offset = row["offset"]
                if offset < len(data):
                    raise DsDatabaseException("Offset to low")
                if offset > len(data):
                    data += bytearray(offset - len(data))
                data += bytearray(row["write_data"])

        return data

    def get_region_info(self, region_id):
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT x, y, pointer
                    FROM region_view
                    WHERE region_id = ?
                    LIMIT 1
                    """, (region_id, )):
                return row["x"], row["y"], row["pointer"]

    def get_region_sizes(self, core_x, core_y, core_p):
        regions = dict()
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT region_num, size FROM region_view
                    WHERE x = ? AND y = ? AND processor = ?
                    ORDER BY region_num
                    """, (core_x, core_y, core_p)):
                regions[row["region_num"]] = row["size"]
        return regions

    def get_total_size(self, core_x, core_y, core_p):
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT sum(size) as total FROM region_view
                    WHERE x = ? AND y = ? AND processor = ?
                    LIMIT 1
                    """, (core_x, core_y, core_p)):
                return row["total"]

    def set_base_address(self, core_id, base_address):
        """
        Sets the base address for a core and calculates pointers

        :param int core_id: The id the database has for this core
        :param int base_address: The base address for the whole core
        """
        pointer = (base_address + APP_PTR_TABLE_BYTE_SIZE)
        to_update = []
        with self.transaction() as cursor:
            cursor.execute(
                """
                UPDATE core SET
                    base_address = ?
                WHERE core_id = ?
                """, (base_address, core_id))

            for row in cursor.execute(
                    """
                    SELECT region_id, size
                    FROM region
                    WHERE core_id = ?
                    ORDER BY region_num
                    """, (core_id,)):
                to_update.append((pointer, row["region_id"]))
                pointer += row["size"]

            for pointer, region_id in to_update:
                cursor.execute(
                    """
                    UPDATE region
                    SET pointer = ?
                    WHERE region_id = ?
                    """, (pointer, region_id))

    def get_base_address(self, core_id):
        """
        Gets the base_address for this core

        :param int core_id: The id the database has for this core
        :return: The base address for the whole core
        :rtype: int
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT base_address
                    FROM core
                    WHERE core_id = ?
                    LIMIT 1
                    """, (core_id, )):
                return row["base_address"]

    def get_region_pointers(self, core_id):
        pointers = []
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT region_num, region_id, pointer, processor
                    FROM region_view
                    WHERE core_id = ?
                    ORDER BY region_num
                     """, (core_id,)):
                pointers.append(
                    (row["region_num"], row["region_id"], row["pointer"],
                     row["processor"]))
            return pointers

    def keys(self):
        """
        Yields the keys.

        .. note::
            Do not use the database for anything else while iterating.

        :return: Yields the (x, y, p)
        :rtype: iterable(tuple(int,int,int))
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT x, y, processor FROM core_view
                    """):
                yield (row["x"], row["y"], row["processor"])

    def get_xyp_totalsize(self, core_id):
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT sum(size) as total_size
                    FROM region_view
                    WHERE core_id = ?
                    LIMIT 1
                    """, (core_id,)):
                return row["total_size"]

    def ds_n_cores(self):
        """
        Returns the number for cores there is a data specification saved for.

        :rtype: int
        :raises DsDatabaseException:
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT COUNT(*) as count FROM core
                    LIMIT 1
                    """):
                return row["count"]
        raise DsDatabaseException("Count query failed")

    def info_iteritems(self):
        """
        Yields the keys and values for the Info data.

        .. note::
            A DB transaction may be held while this iterator is processing.
            Reentrant use of this class is not supported.

        :return: Yields the (x, y, p), start_address, memory_used
            and memory_written
        :rtype: iterable(tuple(tuple(int, int, int), int, int, int))
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT
                        x, y, processor,
                        base_address, memory_used, memory_written
                    FROM core_info
                    """):
                yield ((row["x"], row["y"], row["processor"]),
                       row["base_address"], row["memory_used"],
                       row["memory_written"])

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
                with self.transaction() as cur:
                    job._write_session_credentials_to_db(cur)

    def get_too_big(self):
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT
                        x, y, processor, region_num, size, data_size
                    FROM write_too_big
                    """):
                yield (row["x"], row["y"], row["processor"],
                       row["region_num"], row["size"], row["data_size"])
