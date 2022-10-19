# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sqlite3
import time
from spinn_utilities.abstract_context_manager import AbstractContextManager
from spinn_utilities.overrides import overrides
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB
from .abstract_database import AbstractDatabase

_DDL_FILE = os.path.join(os.path.dirname(__file__), "db.sql")
_SECONDS_TO_MICRO_SECONDS_CONVERSION = 1000

#: Name of the database in the data folder
DB_FILE_NAME = "buffer.sqlite3"


def _timestamp():
    return int(time.time() * _SECONDS_TO_MICRO_SECONDS_CONVERSION)


class SqlLiteDatabase(SQLiteDB, AbstractContextManager):
    """ Specific implementation of the Database for SQLite 3.

    .. note::
        *Not thread safe on the same database file!*
        Threads can access different DBs just fine.
    """

    __slots__ = []

    def __init__(self, database_file=None):
        """
        :param str database_file:
            The name of a file that contains (or will contain) an SQLite
            database holding the data.
            If omitted the default location will be used
        """
        if database_file is None:
            database_file = self.default_database_file()

        super().__init__(database_file, ddl_file=_DDL_FILE)

    def default_database_file(self):
        return os.path.join(
            FecDataView.get_run_dir_path(), DB_FILE_NAME)

    @overrides(AbstractDatabase.clear)
    def clear(self):
        with self.transaction() as cursor:
            cursor.execute(
                """
                UPDATE region SET
                    content = CAST('' AS BLOB), content_len = 0,
                    fetches = 0, append_time = NULL
                """)
            cursor.execute("DELETE FROM region_extra")

    @overrides(AbstractDatabase.clear_region)
    def clear_region(self, x, y, p, region):
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT region_id FROM region_view
                    WHERE x = ? AND y = ? AND processor = ?
                        AND local_region_index = ? AND fetches > 0 LIMIT 1
                    """, (x, y, p, region)):
                locus = (row["region_id"], )
                break
            else:
                return False
            cursor.execute(
                """
                UPDATE region SET
                    content = CAST('' AS BLOB), content_len = 0,
                    fetches = 0, append_time = NULL
                WHERE region_id = ?
                """, locus)
            cursor.execute(
                """
                DELETE FROM region_extra WHERE region_id = ?
                """, locus)
            return True

    def __read_contents(self, cursor, x, y, p, region):
        """
        :param ~sqlite3.Cursor cursor:
        :param int x:
        :param int y:
        :param int p:
        :param int region:
        :rtype: memoryview
        """
        for row in cursor.execute(
                """
                SELECT region_id, content, have_extra
                FROM region_view
                WHERE x = ? AND y = ? AND processor = ?
                    AND local_region_index = ? LIMIT 1
                """, (x, y, p, region)):
            r_id, data, extra = (
                row["region_id"], row["content"], row["have_extra"])
            break
        else:
            raise LookupError("no record for region ({},{},{}:{})".format(
                x, y, p, region))
        if extra:
            c_buffer = None
            for row in cursor.execute(
                    """
                    SELECT r.content_len + (
                        SELECT SUM(x.content_len)
                        FROM region_extra AS x
                        WHERE x.region_id = r.region_id) AS len
                    FROM region AS r WHERE region_id = ? LIMIT 1
                    """, (r_id, )):
                c_buffer = bytearray(row["len"])
                c_buffer[:len(data)] = data
            idx = len(data)
            for row in cursor.execute(
                    """
                    SELECT content FROM region_extra
                    WHERE region_id = ? ORDER BY extra_id ASC
                    """, (r_id, )):
                item = row["content"]
                c_buffer[idx:idx + len(item)] = item
                idx += len(item)
            data = c_buffer
        return memoryview(data)

    @staticmethod
    def __get_core_id(cursor, x, y, p):
        """
        :param ~sqlite3.Cursor cursor:
        :param int x:
        :param int y:
        :param int p:
        :rtype: int
        """
        for row in cursor.execute(
                """
                SELECT core_id FROM region_view
                WHERE x = ? AND y = ? AND processor = ?
                LIMIT 1
                """, (x, y, p)):
            return row["core_id"]
        cursor.execute(
            """
            INSERT INTO core(x, y, processor) VALUES(?, ?, ?)
            """, (x, y, p))
        return cursor.lastrowid

    def __get_region_id(self, cursor, x, y, p, region):
        """
        :param ~sqlite3.Cursor cursor:
        :param int x:
        :param int y:
        :param int p:
        :param int region:
        """
        for row in cursor.execute(
                """
                SELECT region_id FROM region_view
                WHERE x = ? AND y = ? AND processor = ?
                    AND local_region_index = ?
                LIMIT 1
                """, (x, y, p, region)):
            return row["region_id"]
        core_id = self.__get_core_id(cursor, x, y, p)
        cursor.execute(
            """
            INSERT INTO region(
                core_id, local_region_index, content, content_len, fetches)
            VALUES(?, ?, CAST('' AS BLOB), 0, 0)
            """, (core_id, region))
        return cursor.lastrowid

    @overrides(AbstractDatabase.store_data_in_region_buffer)
    def store_data_in_region_buffer(self, x, y, p, region, missing, data):
        # pylint: disable=too-many-arguments, unused-argument
        # TODO: Use missing
        datablob = sqlite3.Binary(data)
        with self.transaction() as cursor:
            region_id = self.__get_region_id(cursor, x, y, p, region)
            if self.__use_main_table(cursor, region_id):
                cursor.execute(
                    """
                    UPDATE region SET
                        content = CAST(? AS BLOB),
                        content_len = ?,
                        fetches = fetches + 1,
                        append_time = ?
                    WHERE region_id = ?
                    """, (datablob, len(data), _timestamp(), region_id))
            else:
                cursor.execute(
                    """
                    UPDATE region SET
                        fetches = fetches + 1,
                        append_time = ?
                    WHERE region_id = ?
                    """, (_timestamp(), region_id))
                assert cursor.rowcount == 1
                cursor.execute(
                    """
                    INSERT INTO region_extra(
                        region_id, content, content_len)
                    VALUES (?, CAST(? AS BLOB), ?)
                    """, (region_id, datablob, len(data)))
                assert cursor.rowcount == 1

    def __use_main_table(self, cursor, region_id):
        """
        :param ~sqlite3.Cursor cursor:
        :param int region_id:
        """
        for row in cursor.execute(
                """
                SELECT COUNT(*) AS existing FROM region
                WHERE region_id = ? AND fetches = 0
                LIMIT 1
                """, (region_id, )):
            existing = row["existing"]
            return existing == 1
        return False

    @overrides(AbstractDatabase.get_region_data)
    def get_region_data(self, x, y, p, region):
        try:
            with self.transaction() as cursor:
                data = self.__read_contents(cursor, x, y, p, region)
                # TODO missing data
                return data, False
        except LookupError:
            return memoryview(b''), True

    def store_placements(self):
        exists = False
        with self.transaction() as cursor:
            for row in cursor.execute("PRAGMA TABLE_INFO(core)"):
                if row["name"] == "label":
                    exists = True

            if exists:
                return
                # already done so no need to repeat

            cursor.execute("ALTER TABLE core ADD COLUMN label STRING")

            for placement in FecDataView.iterate_placemements():
                core_id = self.__get_core_id(
                    cursor, placement.x, placement.y, placement.p)
                cursor.execute(
                    "UPDATE core SET label = ? WHERE core_id = ?",
                    (placement.vertex.label, core_id))
                assert cursor.rowcount == 1

    def get_label(self, x, y, p):
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT label
                    FROM core
                    WHERE x = ? AND y = ? and processor = ?
                    """, (x, y, p)):
                return str(row["label"], 'utf8')
        return ""

    def store_chip_power_monitors(self):
        # delayed import due to circular refrences
        from spinn_front_end_common.utility_models.\
            chip_power_monitor_machine_vertex import (
                ChipPowerMonitorMachineVertex)

        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='chip_power_monitor'
                     """):
                # Already exists so no need to run again
                return

            cursor.execute(
                """
                CREATE TABLE chip_power_monitors(
                    cpm_id INTEGER PRIMARY KEY autoincrement,
                    core_id INTEGER NOT NULL
                        REFERENCES core(core_id) ON DELETE RESTRICT,
                    sampling_frequency  FLOAT NOT NULL)
                """)

            cursor.execute(
                """
                CREATE VIEW chip_power_monitors_view AS
                SELECT core_id, x, y, processor, sampling_frequency
                    FROM core NATURAL JOIN chip_power_monitors
                """)

            for placement in FecDataView.iterate_placements_by_vertex_type(
                    ChipPowerMonitorMachineVertex):
                core_id = self.__get_core_id(
                    cursor, placement.x, placement.y, placement.p)
                cursor.execute(
                    """
                    INSERT INTO chip_power_monitors(
                        core_id, sampling_frequency)
                    VALUES (?, ?)
                    """, (core_id, placement.vertex.sampling_frequency))
                assert cursor.rowcount == 1

    def iterate_chip_power_monitor_cores(self):
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT x, y, processor, sampling_frequency
                    FROM chip_power_monitors_view
                    ORDER BY core_id
                    """):
                yield row
