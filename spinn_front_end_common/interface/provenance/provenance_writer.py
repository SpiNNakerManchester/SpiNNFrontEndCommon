# Copyright (c) 2017-2022 The University of Manchester
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

from datetime import datetime
import logging
import os
from spinn_utilities.abstract_context_manager import AbstractContextManager
from spinn_utilities.config_holder import get_config_int
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.constants import (
    MICRO_TO_MILLISECOND_CONVERSION)
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB
from .provenance_base import ProvenanceBase

logger = FormatAdapter(logging.getLogger(__name__))

_MAPPING_DDL = os.path.join(os.path.dirname(__file__), "mapping.sql")
_GLOBAL_DDL = os.path.join(os.path.dirname(__file__), "global.sql")


class ProvenanceWriter(AbstractContextManager, ProvenanceBase):
    """ Specific implementation of the Database for SQLite 3.

    .. note::
        *Not thread safe on the same database file.*
        Threads can access different DBs just fine.

    .. note::
        This totally relies on the way SQLite's type affinities function.
        You can't port to a different database engine without a lot of work.
    """

    __slots__ = [
        "_global_db",
        "_global_data_path",
        "_mapping_db",
        "_mapping_data_path"
    ]

    def __init__(self, global_data_path=None, mapping_data_path=None):
        """
        Records the paths (if any) to the databases.

        This does not create the database so at least the first call to
        ProvenanceWriter should also call create_tables method

        This avoids all further ProvenanceWriter to have to run the DDL files.

        :param global_data_path:
            The name of a file that contains (or will contain) an SQLite
            database holding the data for the whole setup to end
            If omitted, the default file path will be used.
        :type global_data_path: str or None
        :param mapping_data_path:
            The name of a file that contains (or will contain) an SQLite
            database holding the data for a single (mapping) run
            If omitted, the default file path will be used.
        :type mapping_data_path: str or None
        """
        self._global_db = None
        self._global_data_path = global_data_path
        self._mapping_db = None
        self._mapping_data_path = mapping_data_path

    def __del__(self):
        self.close()

    def create_tables(self):
        """
        Creates the tables by running the DDL files.

        This can also be used to create adatabase with all tables empty.

        """
        if self._global_db is None:
            if self._global_data_path is None:
                self._global_data_path = self.get_last_global_database_path()
            self._global_db = SQLiteDB(
                self._global_data_path, ddl_file=_GLOBAL_DDL)
        if self._mapping_db is None:
            if self._mapping_data_path is None:
                self._mapping_data_path = self.get_last_run_database_path()
            self._mapping_db = SQLiteDB(
                self._mapping_data_path, ddl_file=_MAPPING_DDL)

    def close(self):
        if self._global_db is not None:
            self._global_db.close()
            self._global_db = None
        if self._mapping_db is not None:
            self._mapping_db.close()
            self._mapping_db = None

    def _global_transaction(self):
        if self._global_db is None:
            if self._global_data_path is None:
                self._global_data_path = self.get_last_global_database_path()
            self._global_db = SQLiteDB(self._global_data_path)
        return self._global_db.transaction()

    def _mapping_transaction(self):
        if self._mapping_db is None:
            if self._mapping_data_path is None:
                self._mapping_data_path = self.get_last_run_database_path()
            self._mapping_db = SQLiteDB(self._mapping_data_path)
        return self._mapping_db.transaction()

    def insert_version(self, description, the_value):
        """
        Inserts data into the version_provenance table

        :param str description: The package for which the version applies
        :param str the_value: The version to be recorded
        """
        with self._global_transaction() as cur:
            cur.execute(
                """
                INSERT INTO version_provenance(
                    description, the_value)
                VALUES(?, ?)
                """, [description, the_value])

    def insert_power(self, description, the_value):
        """
        Inserts a general power value into the power_provenane table

        :param str description: Type of value
        :param float the_value: data
        """
        with self._mapping_transaction() as cur:
            cur.execute(
                """
                INSERT INTO power_provenance(
                    description, the_value)
                VALUES(?, ?)
                """, [description, the_value])

    def insert_category(self, category, machine_on):
        """
        Inserts category into the category_timer_provenance  returning id

        :param TimerCategory category: Name of Category starting
        :param bool machine_on: If the machine was done during all
            or some of the time
        """
        with self._global_transaction() as cur:
            cur.execute(
                """
                INSERT INTO category_timer_provenance(
                    category, machine_on, n_run, n_loop)
                VALUES(?, ?, ?, ?)
                """,
                [category.category_name, machine_on,
                 FecDataView.get_run_number(),
                 FecDataView.get_run_step()])
            return cur.lastrowid

    def insert_category_timing(self, category_id, timedelta):
        """
        Inserts run time into the category

        :param int category_id: id of the Category finished
        :param ~datetime.timedelta timedelta: Time to be recorded
       """
        time_taken = (
                (timedelta.seconds * MICRO_TO_MILLISECOND_CONVERSION) +
                (timedelta.microseconds / MICRO_TO_MILLISECOND_CONVERSION))

        with self._global_transaction() as cur:
            cur.execute(
                """
                UPDATE category_timer_provenance
                SET
                    time_taken = ?
                WHERE category_id = ?
                """, (time_taken, category_id))

    def insert_timing(
            self, category, algorithm, work, timedelta, skip_reason):
        """
        Inserts algorithms run times into the timer_provenance table

        :param int category: Category Id of the Algorithm
        :param str algorithm: Algorithm name
        :param TimerWork work: Type of work being done
        :param ~datetime.timedelta timedelta: Time to be recorded
        :param skip_reason: The reason the algorthm was skipped or None if
            it was not skipped
        :tpye skip_reason: str or None
        """
        time_taken = (
                (timedelta.seconds * MICRO_TO_MILLISECOND_CONVERSION) +
                (timedelta.microseconds / MICRO_TO_MILLISECOND_CONVERSION))
        with self._global_transaction() as cur:
            cur.execute(
                """
                INSERT INTO timer_provenance(
                    category_id, algorithm, work, time_taken, skip_reason)
                VALUES(?, ?, ?, ?, ?)
                """,
                [category, algorithm, work.work_name, time_taken, skip_reason])

    def insert_gatherer(self, x, y, address, bytes_read, run, description,
                        the_value):
        """
        Records provenance into the gatherer_provenance

        :param int x: X coordinate of the chip
        :param int y: Y coordinate of the chip
        :param int address: sdram address read from
        :param int bytes_read: number of bytes read
        :param int run: run number
        :param str description: type of value
        :param float the_value: data
        """
        with self._mapping_transaction() as cur:
            cur.execute(
                """
                INSERT INTO gatherer_provenance(
                    x, y, address, bytes, run, description, the_value)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """, [x, y, address, bytes_read, run, description, the_value])

    def insert_monitor(self, x, y, description, the_value):
        """
        Inserts data into the monitor_provenance table

        :param int x: X coordinate of the chip
        :param int y: Y coordinate of the chip
        :param str description: type of value
        :param int the_value: data
        """
        with self._mapping_transaction() as cur:
            cur.execute(
                """
                INSERT INTO monitor_provenance(
                    x, y, description, the_value)
                VALUES(?, ?, ?, ?)
                """, [x, y, description, the_value])

    def insert_router(
            self, x, y, description, the_value, expected=True):
        """
        Inserts data into the router provenance table

        :param int x: X coordinate of the chip
        :param int y: Y coordinate of the chip
        :param str description: type of value
        :param float the_value: data
        :param bool expected: Flag to say this data was expected
        """
        with self._mapping_transaction() as cur:
            cur.execute(
                """
                INSERT INTO router_provenance(
                    x, y, description, the_value, expected)
                VALUES(?, ?, ?, ?, ?)
                """, [x, y, description, the_value, expected])

    def insert_core(self, x, y, p, description, the_value):
        """
        Inserts data for a specific core into the core_provenance table

        :param int x: X coordinate of the chip
        :param int y: Y coordinate of the chip
        :param int p: id of the core
        :param str description: type of value
        :param int the_value: data
        """
        with self._mapping_transaction() as cur:
            cur.execute(
                """
                INSERT INTO core_provenance(
                    x, y, p, description, the_value)
                VALUES(?, ?, ?, ?, ?)
                """, [x, y, p, description, the_value])

    def add_core_name(self, x, y, p, core_name):
        """
        Adds a vertex or similar name for the core to the core_mapping table

        A second call to the same core is silently ignored even if the name
        if different.

        :param int x: X coordinate of the chip
        :param int y: Y coordinate of the chip
        :param int p: id of the core
        :param str core_name: Name to assign
        """
        with self._mapping_transaction() as cur:
            cur.execute(
                """
                INSERT OR IGNORE INTO core_mapping(
                    x, y, p, core_name)
                VALUES(?, ?, ?, ?)
                """, [x, y, p, core_name])

    def insert_report(self, message):
        """
        Save and if applicable logs a message to the report_table

        Only logs the messages up to the cutoff set by
        cfg provenance_report_cutoff

        :param str message:
        """
        with self._mapping_transaction() as cur:
            cur.execute(
                """
                INSERT INTO reports(message)
                VALUES(?)
                """, [message])
            recorded = cur.lastrowid
        cutoff = get_config_int("Reports", "provenance_report_cutoff")
        if cutoff is None or recorded < cutoff:
            logger.warning(message)
        elif recorded == cutoff:
            logger.warning(f"Additional interesting provenance items in "
                           f"{self._mapping_data_path}")

    def insert_connector(
            self, pre_population, post_population, the_type, description,
            the_value):
        """
        Inserts edge data into the connector_provenance

        :param str pre_population: Name of the pre population / vertex
        :param str post_population:  Name of the post population / vertex
        :param str the_type: Class of the connector
        :param str description: type of value
        :param int the_value: data
        """
        with self._mapping_transaction() as cur:
            cur.execute(
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
        Write the conection treived from spalloc job

        :param connections: {(x, y): hostname, ...} or None
        :type connections: dict((int, int): str) or None
        """
        if not connections:
            return
        with self._mapping_transaction() as cursor:
            cursor.executemany(
                """
                INSERT OR IGNORE INTO boards_provenance(
                ethernet_x, ethernet_y, ip_addres)
                VALUES (?, ?, ?)
                """, ((x, y, ipaddress)
                      for ((x, y), ipaddress) in connections.items()))

    def store_log(self, level, message, timestamp=None):
        """
        Stores log messages into the database

        :param int level:
        :param str message:
        """
        if timestamp is None:
            timestamp = datetime.now()
        with self._global_transaction() as cur:
            cur.execute(
                """
                INSERT INTO p_log_provenance(
                    timestamp, level, message)
                VALUES(?, ?, ?)
                """,
                [timestamp, level, message])

    def _test_log_locked(self, text):
        """
        THIS IS A TESTING METHOD.

        This will lock the database and then try to do a log
        """
        with self._global_transaction() as cur:
            # lock the database
            cur.execute(
                """
                INSERT INTO version_provenance(
                    description, the_value)
                VALUES("foo", "bar")
                """)
            cur.lastrowid
            # try logging and storing while locked.
            logger.warning(text)
