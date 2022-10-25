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
from .base_database import BaseDatabase

_DDL_FILE = os.path.join(os.path.dirname(__file__), "db.sql")
_SECONDS_TO_MICRO_SECONDS_CONVERSION = 1000
#: Name of the database in the data folder


def _timestamp():
    return int(time.time() * _SECONDS_TO_MICRO_SECONDS_CONVERSION)


class BufferDatabase(BaseDatabase):
    """ Specific implementation of the Database for SQLite 3.

    There should only ever be a single Database Object in use at any time.
    In the case of application_graph_changed the first should closed and
    a new one created.

    If 2 database objects where opened with the database_file they hold the
    same data. Unless someone else deletes that file.


    .. note::
        *Not thread safe on the same database file!*
        Threads can access different DBs just fine.
    """

    __slots__ = []

    def clear_region(self, x, y, p, region):
        """ Clears the data for a single region.

        .. note::
            This method *loses information!*

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :param int region: Region containing the data to be cleared
        :return: True if any region was changed
        :rtype: bool
        """
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
        core_id = self._get_core_id(cursor, x, y, p)
        cursor.execute(
            """
            INSERT INTO region(
                core_id, local_region_index, content, content_len, fetches)
            VALUES(?, ?, CAST('' AS BLOB), 0, 0)
            """, (core_id, region))
        return cursor.lastrowid

    def store_data_in_region_buffer(self, x, y, p, region, missing, data):
        """ Store some information in the corresponding buffer for a\
            specific chip, core and recording region.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :param int region: Region containing the data to be stored
        :param bool missing: Whether any data is missing
        :param bytearray data: data to be stored

            .. note::
                    Must be shorter than 1GB
        """

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

    def get_region_data(self, x, y, p, region):
        """ Get the data stored for a given region of a given core

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :param int region: Region containing the data
        :return: a buffer containing all the data received during the\
            simulation, and a flag indicating if any data was missing

            .. note::
                Implementations should not assume that the total buffer is
                necessarily shorter than 1GB.

        :rtype: tuple(memoryview, bool)
        """
        try:
            with self.transaction() as cursor:
                data = self.__read_contents(cursor, x, y, p, region)
                # TODO missing data
                return data, False
        except LookupError:
            return memoryview(b''), True
