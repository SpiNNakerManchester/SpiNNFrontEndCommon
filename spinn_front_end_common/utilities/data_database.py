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
import time
from spinn_utilities.abstract_context_manager import AbstractContextManager
from spinn_utilities.config_holder import get_config_int_or_none
from spinn_utilities.log import FormatAdapter
from spinnman.spalloc.spalloc_job import SpallocJob
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB

_DDL_FILE = os.path.join(os.path.dirname(__file__),
                         "db.sql")

_SECONDS_TO_MICRO_SECONDS_CONVERSION = 1000
#: Name of the database in the data folder

logger = FormatAdapter(logging.getLogger(__name__))

def _timestamp():
    return int(time.time() * _SECONDS_TO_MICRO_SECONDS_CONVERSION)


class DataDatabase(SQLiteDB, AbstractContextManager):
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

    def __init__(self, database_file=None, *, read_only=False,
                 row_factory=sqlite3.Row, text_factory=memoryview):
        """
        :param str database_file:
            The name of a file that contains (or will contain) an SQLite
            database holding the data.
            If omitted the default location will be used.
        """
        if database_file is None:
            database_file = os.path.join(
                FecDataView.get_run_dir_path(),
                f"data{FecDataView.get_reset_str()}.sqlite3")
        super().__init__(
            database_file, read_only=read_only, row_factory=row_factory,
            text_factory=text_factory, ddl_file=_DDL_FILE)

    def _get_core_id(self, x, y, p):
        """
        :param int x:
        :param int y:
        :param int p:
        :rtype: int
        """
        for row in self.execute(
                """
                SELECT core_id FROM core
                WHERE x = ? AND y = ? AND processor = ?
                LIMIT 1
                """, (x, y, p)):
            return row["core_id"]
        self.execute(
            """
            INSERT INTO core(x, y, processor) VALUES(?, ?, ?)
            """, (x, y, p))
        return self.lastrowid

    def clear_region(self, x, y, p, region):
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

    def _read_contents(self, region_id):
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

    def _get_region_id(self, x, y, p, region):
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
        return self.lastrowid

    def store_data_in_region_buffer(self, x, y, p, region, missing, data):
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
        datablob = sqlite3.Binary(data)
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

    def __use_main_table(self, region_id):
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

    def get_region_data(self, x, y, p, region):
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

    def write_session_credentials_to_db(self):
        """
        Write Spalloc session credentials to the database if in use.
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

    def _set_core_name(self, x, y, p, core_name):
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
        except sqlite3.IntegrityError:
            self.execute(
                """
                UPDATE core SET core_name = ?
                WHERE x = ? AND y = ? and processor = ?
                """, (core_name, x, y, p))

    def store_vertex_labels(self):
        for placement in FecDataView.iterate_placemements():
            self._set_core_name(placement.x, placement.y,
                                placement.p, placement.vertex.label)
        for chip in FecDataView.get_machine().chips:
            for processor in chip.processors:
                if processor.is_monitor:
                    self._set_core_name(
                        chip.x, chip.y, processor.processor_id,
                        f"SCAMP(OS)_{chip.x}:{chip.y}")

    def get_core_name(self, x, y, p):
        for row in self.execute(
                """
                SELECT core_name
                FROM core
                WHERE x = ? AND y = ? and processor = ?
                """, (x, y, p)):
            return str(row["core_name"], 'utf8')

    def insert_power(self, description, the_value):
        """
        Inserts a general power value into the `power_provenance` table.

        :param str description: Type of value
        :param float the_value: data
        """
        self.execute(
            """
            INSERT INTO power_provenance(
                description, the_value)
            VALUES(?, ?)
            """, [description, the_value])

    def insert_gatherer(self, x, y, address, bytes_read, run, description,
                        the_value):
        """
        Records provenance into the `gatherer_provenance` table.

        :param int x: X coordinate of the chip
        :param int y: Y coordinate of the chip
        :param int address: SDRAM address read from
        :param int bytes_read: number of bytes read
        :param int run: run number
        :param str description: type of value
        :param float the_value: data
        """
        self.execute(
            """
            INSERT INTO gatherer_provenance(
                x, y, address, bytes, run, description, the_value)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """, [x, y, address, bytes_read, run, description, the_value])

    def insert_monitor(self, x, y, description, the_value):
        """
        Inserts data into the `monitor_provenance` table.

        :param int x: X coordinate of the chip
        :param int y: Y coordinate of the chip
        :param str description: type of value
        :param int the_value: data
        """
        self.execute(
            """
            INSERT INTO monitor_provenance(
                x, y, description, the_value)
            VALUES(?, ?, ?, ?)
            """, [x, y, description, the_value])

    def insert_router(
            self, x, y, description, the_value, expected=True):
        """
        Inserts data into the `router_provenance` table.

        :param int x: X coordinate of the chip
        :param int y: Y coordinate of the chip
        :param str description: type of value
        :param float the_value: data
        :param bool expected: Flag to say this data was expected
        """
        self.execute(
            """
            INSERT INTO router_provenance(
                x, y, description, the_value, expected)
            VALUES(?, ?, ?, ?, ?)
            """, [x, y, description, the_value, expected])

    def insert_core(self, x, y, p, description, the_value):
        """
        Inserts data for a specific core into the `core_provenance` table.

        :param int x: X coordinate of the chip
        :param int y: Y coordinate of the chip
        :param int p: ID of the core
        :param str description: type of value
        :param int the_value: data
        """
        core_id = self._get_core_id(x, y, p)
        self.execute(
            """
            INSERT INTO core_provenance(
                core_id, description, the_value)
            VALUES(?, ?, ?)
            """, [core_id, description, the_value])

    def insert_report(self, message):
        """
        Save and if applicable logs a message to the `reports` table.

        Only logs the messages up to the cut-off set by
        configuration `provenance_report_cutoff`

        :param str message:
        """
        self.execute(
            """
            INSERT INTO reports(message)
            VALUES(?)
            """, [message])
        recorded = self.lastrowid
        cutoff = get_config_int_or_none("Reports", "provenance_report_cutoff")
        if cutoff is None or recorded < cutoff:
            logger.warning(message)
        elif recorded == cutoff:
            logger.warning(f"Additional interesting provenance items in "
                           f"{self._database_file}")

    def insert_connector(
            self, pre_population, post_population, the_type, description,
            the_value):
        """
        Inserts edge data into the `connector_provenance`

        :param str pre_population: Name of the pre-population / vertex
        :param str post_population: Name of the post-population / vertex
        :param str the_type: Class of the connector
        :param str description: type of value
        :param int the_value: data
        """
        self.execute(
            """
            INSERT OR IGNORE INTO connector_provenance(
                pre_population, post_population, the_type, description,
                the_value)
            VALUES(?, ?, ?, ?, ?)
            """,
            [pre_population, post_population, the_type, description,
             the_value])

    def insert_board_provenance(self, connections):
        """
        Write the connection details retrieved from spalloc_client job to the
        `boards_provenance` table.

        :param connections: {(x, y): hostname, ...} or None
        :type connections: dict((int, int): str) or None
        """
        if not connections:
            return
        self.executemany(
            """
            INSERT OR IGNORE INTO boards_provenance(
            ethernet_x, ethernet_y, ip_addres)
            VALUES (?, ?, ?)
            """, ((x, y, ipaddress)
                  for ((x, y), ipaddress) in connections.items()))

    def run_query(self, query, params=()):
        """
        Opens a connection to the database, runs a query, extracts the results
        and closes the connection.

        The return type depends on the use_sqlite_rows parameter.
        By default this method returns tuples (lookup by index) but the
        advanced tuple type can be used instead, which supports lookup by name
        used in the query (use ``AS name`` in the query to set).

        This method will not allow queries that change the database unless the
        read_only flag is set to False.

        .. note::
            This method is mainly provided as a support method for the later
            methods that return specific data. For new IntergationTests
            please add a specific method rather than call this directly.

        :param str query: The SQL query to be run. May include ``?`` wildcards
        :param ~collections.abc.Iterable(str or int) params:
            The values to replace the ``?`` wildcards with.
            The number and types must match what the query expects
        :param bool read_only: see :py:meth:`get_database_handle`
        :param bool use_sqlite_rows: see :py:meth:`get_database_handle`
        :return: A list possibly empty of tuples/rows
            (one for each row in the database)
            where the number and type of the values corresponds to the where
            statement
        :rtype: list(tuple or ~sqlite3.Row)
        """

        results = []
        a = self.execute(query, params)
        for row in a:
            results.append(row)
        return results

    def cores_with_late_spikes(self):
        """
        Gets the x, y, p and count of the cores where late spikes arrived.

        Cores that received spikes but where none were late are *not* included.

        :return: A list hopefully empty of tuples (x, y, p, count) of cores
            where their where late arriving spikes.
        :rtype: list(tuple(int, int, int, int))
        """
        query = """
            SELECT x, y, p, the_value AS "value"
            FROM core_provenance
            WHERE description = 'Number_of_late_spikes'
                AND the_value > 0
            """
        return self.run_query(query)

    def get_provenance_for_router(self, x, y):
        """
        Gets the provenance item(s) from the last run relating to a chip.

        :param int x:
            The X coordinate of the chip
        :param int y:
            The Y coordinate of the chip
        :return:
            A possibly multi-line string with for each row which matches the
            like a line ``description_name: value``
        :rtype: str
        """
        query = """
            SELECT
                description,
                sum(the_value) AS "value"
            FROM router_provenance
            WHERE x = ? AND y = ?
            GROUP BY description
            ORDER BY description
            """
        result = "\n".join(
            f"{ row[0] }: { row[1] }"
            for row in self.run_query(query, [int(x), int(y)]))
        return result

    def get_cores_with_provenace(self):
        """
        Gets the cores with provenance.

        :return: A list tuples (x, y, p)
        :rtype: list(tuple(int, int, int))
        """
        query = """
            SELECT core_name, x, y, p
            FROM core_provenance_view
            group by x, y, p
            """
        return self.run_query(query)

    def get_router_by_chip(self, description):
        """
        Gets the router values for a specific item.

        :param str description:
        :return: list of tuples x, y, value)
        :rtype: list(tuple(int, int, float))
        """
        query = """
            SELECT x, y, the_value
            FROM router_provenance
            WHERE description = ?
            """
        data = self.run_query(query, [description])
        try:
            return data
        except IndexError:
            return None

    def get_monitor_by_chip(self, description):
        """
        Gets the monitor values for a specific item.

        :param str description:
        :return: list of tuples x, y, value)
        :rtype: list(tuple(int, int, float))
        """
        query = """
            SELECT x, y, the_value
            FROM monitor_provenance
            WHERE description = ?
            """
        data = self.run_query(query, [description])
        try:
            return data
        except IndexError:
            return None

    def messages(self):
        """
        List all the provenance messages.

        :return: all messages logged or not; order is whatever the DB chooses
        :rtype: list(str)
        """
        query = """
             SELECT message
             FROM reports
             """
        return self.run_query(query, [])

    @staticmethod
    def demo():
        """
        A demonstration of how to use this class.

        See also `unittests/interface/provenance/test_provenance_database.py`
        """
        # This uses the example file in the same directory as this script
        with ProvenanceReader(os.path.join(
                os.path.dirname(__file__), "provenance.sqlite3")) as pr:
            print("DIRECT QUERY:")
            query = """
                SELECT x, y, the_value
                FROM router_provenance
                WHERE description = 'Local_P2P_Packets'
                """
            results = pr.run_query(query)
            for row in results:
                print(row)
            print("\nCORES WITH LATE SPIKES:")
            print(pr.cores_with_late_spikes())
            print("\nROUETER (0,0) PROVENANCE:")
            print(pr.get_provenance_for_router(0, 0))
            print("\nCORES WITH PROVENACE")
            print(pr.get_cores_with_provenace())


if __name__ == '__main__':
    ProvenanceReader.demo()
