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

import io
import logging
import numpy
import os
import sqlite3
from spinn_utilities.log import FormatAdapter
from spinnman.model.enums import ExecutableType
from spinnman.spalloc.spalloc_job import SpallocJob
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.constants import (
    APP_PTR_TABLE_HEADER_BYTE_SIZE, MAX_MEM_REGIONS, TABLE_TYPE)
from spinn_front_end_common.utilities.exceptions import DsDatabaseException
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB

_DDL_FILE = os.path.join(os.path.dirname(__file__), "dse.sql")
logger = FormatAdapter(logging.getLogger(__name__))

# Stop large numbers being written as blobs

sqlite3.register_adapter(numpy.int64, lambda val: int(val))
sqlite3.register_adapter(numpy.int32, lambda val: int(val))


class DsSqlliteDatabase(SQLiteDB):
    """
    A database for holding data specification details.
    """
    __slots__ = [
        # The root ethernet id if required
        "__root_ethernet_id"
    ]

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
            self.__init_db_contents()
        self.__root_ethernet_id = self.__find_root_id()

    @classmethod
    def default_database_file(cls):
        return os.path.join(FecDataView.get_run_dir_path(),
                            f"ds{FecDataView.get_reset_str()}.sqlite3")

    def __init_db_contents(self):
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

    def __find_root_id(self):
        first_x = first_y = root_id = None
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT ethernet_id, ethernet_x, ethernet_y FROM ethernet
                    ORDER BY ethernet_x, ethernet_y
                    LIMIT 1
                    """):
                root_id = row["ethernet_id"]
                first_x = row["ethernet_x"]
                first_y = row["ethernet_y"]
        if root_id is None:
            # Should only be reachable for an empty machine
            raise DsDatabaseException("No ethernet chip found")
        if first_x or first_y:
            logger.warning(
                "No Ethernet chip found at 0,0 using {},{} "
                "for all boards with no IP address.", first_x, first_y)
        return root_id

    def get_core_id(self, core_x, core_y, core_p, vertex):
        """
        Gets the database core_id for the core with this x,y,z

        Will create a new database core record if required.

        :param int core_x:
            X coordinate of the core that `spec_bytes` applies to
        :param int core_y:
            Y coordinate of the core that `spec_bytes` applies to
        :param int p: Processor ID of the core that `spec_bytes` applies to
        :type vertex:
            ~spinn_front_end_common.abstract_models.AbstractRewritesDataSpecification
        :rtype: int
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT core_id 
                    FROM core_view
                    WHERE x = ? AND y = ? AND processor = ?
                    LIMIT 1
                    """, (core_x, core_y, core_p)):
                return row["core_id"]
            if vertex is None:
                raise DsDatabaseException(
                    f"No region known for {core_x} {core_y} {core_p}")
            chip_id = self._get_chip_id(cursor, core_x, core_y)
            if vertex.get_binary_start_type() == ExecutableType.SYSTEM:
                is_system = 1
            else:
                is_system = 0
            cursor.execute(
                """
                INSERT INTO core(chip_id, processor, is_system) 
                VALUES(?, ?, ?)
                """, (chip_id, core_p, is_system))
            return cursor.lastrowid

    def get_core_infos(self, is_system):
        with self.transaction() as cursor:
            core_infos = []
            for row in cursor.execute(
                    """
                    SELECT core_id, x, y, processor
                    FROM core_view
                    WHERE is_system = ?
                    ORDER BY core_id
                     """, (is_system,)):
                core_infos.append(
                    (row["core_id"], row["x"], row["y"], row["processor"]))
        return core_infos

    def _get_chip_id(self, cursor, core_x, core_y):
        """
        :param ~sqlite3.Cursor cursor:
        :param int core_x:
        :param int core_y:
        :rtype: int
        """
        for row in cursor.execute(
                """
                SELECT chip_id FROM chip
                WHERE x = ? AND y = ?
                LIMIT 1
                """, (core_x, core_y)):
            return row["chip_id"]
        ethernet_id = self.get_ethernet_id(cursor, core_x, core_y)
        cursor.execute(
            """
            INSERT INTO chip(x, y, ethernet_id) VALUES(?, ?, ?)
            """, (core_x, core_y, ethernet_id))
        return cursor.lastrowid

    def get_ethernet_id(self, cursor, core_x, core_y):
        chip = FecDataView().get_chip_at(core_x, core_y)
        for row in cursor.execute(
                """
                SELECT ethernet_id FROM ethernet
                WHERE ethernet_x = ? AND ethernet_y = ?
                LIMIT 1
                """, (chip.nearest_ethernet_x, chip.nearest_ethernet_y)):
            return row["ethernet_id"]
        return self.__root_ethernet_id

    def write_memory_region(
            self, core_id, region_num, size, reference, label):
        with self.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO region(
                    core_id, region_num, size, reference_num, region_label) 
                VALUES(?, ?, ?, ?, ?)
                """, (core_id, region_num, size, reference, label))
            return cursor.lastrowid

    def get_memory_region(self, core_id, region_num):
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT region_id, size FROM region
                    WHERE core_id = ? AND region_num = ?
                    LIMIT 1
                    """, (core_id, region_num)):
                return row["region_id"], row["size"]
        raise DsDatabaseException(f"Region {region_num} not set")

    def write_reference(self, core_id, region_num, reference):
        with self.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO reference(core_id, region_num, reference_num) 
                VALUES(?, ?, ?)
                """, (core_id, region_num, reference))
            return cursor.lastrowid

    def get_reference_pointers(self, core_id):
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT reference.region_num, pointer
                    FROM reference JOIN region
                    ON reference.reference_num = region.reference_num
                    WHERE reference.core_id = ?
                    """, (core_id,)):
                yield row["region_num"], row["pointer"]

    def set_write_data(self, region_id, offset, write_data, data_debug):
        with self.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO write(
                    region_id,  offset, write_data, data_debug) 
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
                    data += bytearray(offset- len(data))
                data += bytearray(row["write_data"])

        return data

    def get_region_size(self, region_id):
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT size 
                    FROM region
                    WHERE region_id = ?
                    LIMIT 1
                    """, (region_id, )):
                return row["size"]

    def get_region_info(self, region_id):
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT x, y, pointer, size 
                    FROM region_view
                    WHERE region_id = ?
                    LIMIT 1
                    """, (region_id, )):
                return row["x"], row["y"], row["pointer"], row["size"]

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
        pointer = (base_address + MAX_MEM_REGIONS * TABLE_TYPE.itemsize +
                   APP_PTR_TABLE_HEADER_BYTE_SIZE)
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
                    SELECT region_num, region_id, pointer
                    FROM region_view
                    WHERE core_id = ?
                    ORDER BY region_num
                     """, (core_id,)):
                pointers.append(
                    (row["region_num"], row["region_id"], row["pointer"]))
            return pointers

    def write_data_spec(self, core_x, core_y, core_p, spec_bytes):
        """
        :param int core_x:
            X coordinate of the core that `spec_bytes` applies to
        :param int core_y:
            Y coordinate of the core that `spec_bytes` applies to
        :param int p: Processor ID of the core that `spec_bytes` applies to
        :param bytes spec_bytes: the data specification byte-code
        """
        old = 1/0
        chip = FecDataView().get_chip_at(core_x, core_y)
        with self.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO core(
                    x, y, processor, content, ethernet_id, app_id)
                VALUES(?, ?, ?, ?, (
                    SELECT COALESCE((
                        SELECT ethernet_id FROM ethernet
                        WHERE ethernet_x = ? AND ethernet_y = ?
                    ), ?)), ?)
                """, (
                    core_x, core_y, core_p, sqlite3.Binary(spec_bytes),
                    chip.nearest_ethernet_x, chip.nearest_ethernet_y,
                    self.__root_ethernet_id, FecDataView().get_app_id()))

    def get_ds(self, x, y, p):
        """
        Retrieves the data specification as byte-code for this core.

        :param int x: core X coordinate
        :param int y: core Y coordinate
        :param int p: core processor ID
        :return: data specification as byte code
        :rtype: bytes
        """
        old = 1/0
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT content FROM core
                    WHERE x = ? AND y = ? AND processor = ?
                    LIMIT 1
                    """, (x, y, p)):
                return row["content"]
        return b""

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

    def items(self):
        """
        Yields the keys and values for the data specification data.

        .. note::
            Do not use the database for anything else while iterating.

        :return:
            Yields the (x, y, p) and saved data specification byte-code pairs
        :rtype: iterable(tuple(tuple(int,int,int),~io.RawIOBase))
        """
        old = 1/0
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT x, y, processor, content FROM core
                    WHERE content IS NOT NULL
                    """, (Exx, y, p)):
                yield ((row["x"], row["y"], row["processor"]),
                       io.BytesIO(row["content"]))

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

    def system_items(self):
        """
        Yields the keys and values for the data specification data for system
        cores.

        .. note::
            Do not use the database for anything else while iterating.

        :return: Yields the (x, y, p), saved data specification byte-code, and
            region_size triples
        :rtype: iterable(tuple(tuple(int,int,int),~io.RawIOBase, int))
        """
        broken = 1/0
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT x, y, processor, sum(size) as total FROM region_view
                    WHERE executable_type = ?
                    GROUP BY x, y, processor
                    """, (ExecutableType.SYSTEM.value,)):
                yield ((row["x"], row["y"], row["processor"]), row["total"])

    def app_items(self):
        """
        Yields the keys and values for the data specification data for
        application cores.

        .. note::
            Do not use the database for anything else while iterating.

        :return:
            Yields the (x, y, p) and saved data specification byte-code pairs
        :rtype: iterable(tuple(tuple(int,int,int),~io.RawIOBase, int))
        """
        old = 1/0
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT x, y, processor, content, memory_used  FROM core
                    WHERE content IS NOT NULL AND is_system = 0
                    """):
                yield ((row["x"], row["y"], row["processor"]),
                       io.BytesIO(row["content"]), row["memory_used"])

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

    def ds_n_app_cores(self):
        """
        Returns the number for application cores there is a data specification
        saved for.

        :rtype: int
        :raises DsDatabaseException:
        """
        old = 1/0
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT COUNT(*) as count FROM core
                    WHERE content IS NOT NULL AND is_system = 0
                    LIMIT 1
                    """):
                return row["count"]
        raise DsDatabaseException("Count query failed")

    def ds_n_system_cores(self):
        """
        Returns the number for system cores there is a data specification
        saved for.

        :rtype: int
        :raises DsDatabaseException:
        """
        not_used = 1/0
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT COUNT(*) as count FROM core
                    WHERE executable_type = ?
                    LIMIT 1
                    """,(ExecutableType.SYSTEM.value,)):
                return row["count"]
        raise DsDatabaseException("Count query failed")

    def set_app_id(self, app_id):
        """
        Sets the same app_id for all rows that have data specification content.

        :param int app_id: value to set
        """
        old = 1/0
        with self.transaction() as cursor:
            cursor.execute(
                """
                UPDATE core SET
                    app_id = ?
                WHERE content IS NOT NULL
                """, (app_id,))

    def get_app_id(self, x, y, p):
        """
        Gets the `app_id` set for this core.

        :param int x: core X coordinate
        :param int y: core Y coordinate
        :param int p: core processor ID
        :rtype: int
        """
        old = 1/0
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT app_id FROM core
                    WHERE x = ? AND y = ? AND processor = ?
                    LIMIT 1
                    """, (x, y, p)):
                return row["app_id"]
        return None

    def get_write_info(self, x, y, p):
        """
        Gets the provenance returned by the data specification executor.

        :param int x: core X coordinate
        :param int y: core Y coordinate
        :param int p: core processor ID
        :return: start_address, memory_used, memory_written
        :rtype: DataWritten
        """
        old = 1/0
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT start_address, memory_used, memory_written
                    FROM core
                    WHERE x = ? AND y = ? AND processor = ?
                    LIMIT 1
                    """, (x, y, p)):
                return (row["start_address"], row["memory_used"],
                        row["memory_written"])
        raise ValueError(f"No info for {x}:{y}:{p}")

    def set_write_info(
            self, x, y, p, start, used, written):
        """
        Sets the provenance returned by the data specification executor.

        :param int x: core X coordinate
        :param int y: core Y coordinate
        :param int p: core processor ID
        :param int start: base address
        :param int used: size allocated
        :param int written: bytes written
        """
        old = 1/0
        with self.transaction() as cursor:
            cursor.execute(
                """
                UPDATE core SET
                    start_address = ?,
                    memory_used = ?,
                    memory_written = ?
                WHERE x = ? AND y = ? AND processor = ?
                """, (start, used, written, x, y, p))
            if cursor.rowcount == 0:
                chip = FecDataView().get_chip_at(x, y)
                cursor.execute(
                    """
                    INSERT INTO core(
                        x, y, processor, start_address,
                        memory_used, memory_written, ethernet_id)
                    VALUES(?, ?, ?, ?, ?, ?, (
                        SELECT COALESCE((
                            SELECT ethernet_id FROM ethernet
                            WHERE ethernet_x = ? AND ethernet_y = ?
                        ), ?)))
                    """, (
                        x, y, p, start, used, written, chip.nearest_ethernet_x,
                        chip.nearest_ethernet_y, self.__root_ethernet_id))

    def set_size_info(self, x, y, p, memory_used):
        old = 1/0
        with self.transaction() as cursor:
            cursor.execute(
                """
                UPDATE core SET
                    memory_used = ?
                WHERE x = ? AND y = ? AND processor = ?
                """, (memory_used, x, y, p))
            if cursor.rowcount == 0:
                chip = FecDataView().get_chip_at(x, y)
                cursor.execute(
                    """
                    INSERT INTO core(
                        x, y, processor, memory_used, ethernet_id)
                    VALUES(?, ?, ?, ?, (
                        SELECT COALESCE((
                            SELECT ethernet_id FROM ethernet
                            WHERE ethernet_x = ? AND ethernet_y = ?
                        ), ?)))
                    """, (
                        x, y, p, int(memory_used),
                        chip.nearest_ethernet_x, chip.nearest_ethernet_y,
                        self.__root_ethernet_id))

    def clear_write_info(self):
        """
        Clears the provenance for all rows.
        """
        old = 1/0
        with self.transaction() as cursor:
            cursor.execute(
                """
                UPDATE core SET
                    start_address = NULL,
                    memory_used = NULL,
                    memory_written = NULL
                """)

    def info_n_cores(self):
        """
        Returns the number for cores there is a info saved for.

        :rtype: int
        :raises DsDatabaseException:
        """
        old = 1/0
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT count(*) as count FROM core
                    WHERE start_address IS NOT NULL
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
