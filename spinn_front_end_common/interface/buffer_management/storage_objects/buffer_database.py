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

from sqlite3 import Binary, IntegrityError
import time
from typing import Optional, Tuple
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.base_database import BaseDatabase

_SECONDS_TO_MICRO_SECONDS_CONVERSION = 1000
#: Name of the database in the data folder


def _timestamp():
    return int(time.time() * _SECONDS_TO_MICRO_SECONDS_CONVERSION)


class BufferDatabase(BaseDatabase):
    """
    Specific implementation of the Database for SQLite 3.

    There should only ever be a single Database Object in use at any time.
    In the case of application_graph_changed the first should closed and
    a new one created.

    If 2 database objects where opened with the database_file they hold the
    same data. Unless someone else deletes that file.

    .. note::
        *Not thread safe on the same database file!*
        Threads can access different DBs just fine.
    """

    __slots__ = ()

    def clear_region(self, x: int, y: int, p: int, region: int) -> bool:
        """
        Clears the data for a single region.

        .. note::
            This method *loses information!*

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :param int region: Region containing the data to be cleared
        :return: True if any region was changed
        :rtype: bool
        """
        for row in self.execute(
                """
                SELECT region_id FROM region_view
                WHERE x = ? AND y = ? AND processor = ?
                    AND local_region_index = ? AND fetches > 0 LIMIT 1
                """, (x, y, p, region)):
            locus = (row["region_id"], )
            break
        else:
            return False
        self.execute(
            """
            UPDATE region SET
                content = CAST('' AS BLOB), content_len = 0,
                fetches = 0, append_time = NULL
            WHERE region_id = ?
            """, locus)
        self.execute(
            """
            DELETE FROM region_extra WHERE region_id = ?
            """, locus)
        return True

    def _read_contents(self, region_id: int) -> memoryview:
        """
        :param int region_id:
        :rtype: memoryview
        """
        for row in self.execute(
                """
                SELECT content
                FROM region_view
                WHERE region_id = ?
                LIMIT 1
                """, (region_id,)):
            data = row["content"]
            break
        else:
            raise LookupError(f"no record for region {region_id}")

        c_buffer = None
        for row in self.execute(
                """
                SELECT r.content_len + (
                    SELECT SUM(x.content_len)
                    FROM region_extra AS x
                    WHERE x.region_id = r.region_id) AS len
                FROM region AS r WHERE region_id = ? LIMIT 1
                """, (region_id, )):
            if row["len"] is not None:
                c_buffer = bytearray(row["len"])
                c_buffer[:len(data)] = data

        if c_buffer is not None:
            idx = len(data)
            for row in self.execute(
                    """
                    SELECT content FROM region_extra
                    WHERE region_id = ? ORDER BY extra_id ASC
                    """, (region_id, )):
                item = row["content"]
                c_buffer[idx:idx + len(item)] = item
                idx += len(item)
            data = c_buffer
        return memoryview(data)

    def _get_region_id(self, x: int, y: int, p: int, region: int) -> int:
        """
        :param int x:
        :param int y:
        :param int p:
        :param int region:
        """
        for row in self.execute(
                """
                SELECT region_id FROM region_view
                WHERE x = ? AND y = ? AND processor = ?
                    AND local_region_index = ?
                LIMIT 1
                """, (x, y, p, region)):
            return row["region_id"]
        core_id = self._get_core_id(x, y, p)
        self.execute(
            """
            INSERT INTO region(
                core_id, local_region_index, content, content_len, fetches)
            VALUES(?, ?, CAST('' AS BLOB), 0, 0)
            """, (core_id, region))
        region_id = self.lastrowid
        assert region_id is not None
        return region_id

    def store_data_in_region_buffer(
            self, x: int, y: int, p: int, region: int, missing: bool,
            data: bytes):
        """
        Store some information in the corresponding buffer for a
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
        datablob = Binary(data)
        region_id = self._get_region_id(x, y, p, region)
        if self.__use_main_table(region_id):
            self.execute(
                """
                UPDATE region SET
                    content = CAST(? AS BLOB),
                    content_len = ?,
                    fetches = fetches + 1,
                    append_time = ?
                WHERE region_id = ?
                """, (datablob, len(data), _timestamp(), region_id))
        else:
            self.execute(
                """
                UPDATE region SET
                    fetches = fetches + 1,
                    append_time = ?
                WHERE region_id = ?
                """, (_timestamp(), region_id))
            assert self.rowcount == 1
            self.execute(
                """
                INSERT INTO region_extra(
                    region_id, content, content_len)
                VALUES (?, CAST(? AS BLOB), ?)
                """, (region_id, datablob, len(data)))
        assert self.rowcount == 1

    def __use_main_table(self, region_id: int) -> bool:
        """
        :param int region_id:
        """
        for row in self.execute(
                """
                SELECT COUNT(*) AS existing FROM region
                WHERE region_id = ? AND fetches = 0
                LIMIT 1
                """, (region_id, )):
            existing = row["existing"]
            return existing == 1
        return False

    def get_region_data(self, x: int, y: int, p: int, region: int) -> Tuple[
            memoryview, bool]:
        """
        Get the data stored for a given region of a given core.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :param int region: Region containing the data
        :return:
            A buffer containing all the data received during the
            simulation, and a flag indicating if any data was missing.

            .. note::
                Implementations should not assume that the total buffer is
                necessarily shorter than 1GB.

        :rtype: tuple(memoryview, bool)
        """
        try:
            region_id = self._get_region_id(x, y, p, region)
            data = self._read_contents(region_id)
            # TODO missing data
            return data, False
        except LookupError:
            return memoryview(b''), True

    def write_session_credentials_to_db(self) -> None:
        """
        Write Spalloc session credentials to the database if in use.
        """
        job = FecDataView.get_spalloc_job()
        if job is not None:
            config = job.get_session_credentials_for_db()
            self.executemany(
                """
                INSERT INTO proxy_configuration(kind, name, value)
                VALUES(?, ?, ?)
                """, [(k1, k2, v) for (k1, k2), v in config.items()])

    def _set_core_name(self, x: int, y: int, p: int, core_name: Optional[str]):
        """
        :param int x:
        :param int y:
        :param int p:
        :param str core_name:
        """
        try:
            self.execute(
                """
                INSERT INTO core (x, y, processor, core_name)
                VALUES (?, ?, ? ,?)
                """, (x, y, p, core_name))
        except IntegrityError:
            self.execute(
                """
                UPDATE core SET core_name = ?
                WHERE x = ? AND y = ? and processor = ?
                """, (core_name, x, y, p))

    def store_vertex_labels(self) -> None:
        """
        Goes though all placement an monitor cores to set a label.
        """
        for placement in FecDataView.iterate_placemements():
            self._set_core_name(
                placement.x, placement.y, placement.p, placement.vertex.label)
        for chip in FecDataView.get_machine().chips:
            for p in chip.scamp_processors_ids:
                self._set_core_name(
                    chip.x, chip.y, p, f"SCAMP(OS)_{chip.x}:{chip.y}")

    def get_core_name(self, x: int, y: int, p: int) -> Optional[str]:
        """
        Gets the label (typically vertex label) for this core.

        Returns None if the core at x, y, p is not known.

        :param int x: core x
        :param int y: core y
        :param int p: core p
        :rtype: str or None
        """
        for row in self.execute(
                """
                SELECT core_name
                FROM core
                WHERE x = ? AND y = ? and processor = ?
                """, (x, y, p)):
            return str(row["core_name"], 'utf8')
        return None
