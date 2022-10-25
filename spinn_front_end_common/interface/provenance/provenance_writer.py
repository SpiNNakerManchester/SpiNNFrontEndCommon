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

import logging
import os
import re
from spinn_utilities.config_holder import get_config_int
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.constants import (PROVENANCE_DB)
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB

logger = FormatAdapter(logging.getLogger(__name__))

_DDL_FILE = os.path.join(os.path.dirname(__file__), "local.sql")
_RE = re.compile(r"(\d+)([_,:])(\d+)(?:\2(\d+))?")


class ProvenanceWriter(SQLiteDB):
    """ Specific implementation of the Database for SQLite 3.

    .. note::
        *Not thread safe on the same database file.*
        Threads can access different DBs just fine.

    .. note::
        This totally relies on the way SQLite's type affinities function.
        You can't port to a different database engine without a lot of work.
    """

    __slots__ = [
        "_database_file"
    ]

    def __init__(self, database_file=None, memory=False):
        """
        :param database_file:
            The name of a file that contains (or will contain) an SQLite
            database holding the data.
            If omitted, either the default file path or an unshared in-memory
            database will be used (suitable only for testing).
        :type database_file: str or None
        :param bool memory:
            Flag to say unshared in-memory can be used.
            Otherwise a None file will mean the default should be used

        """
        if database_file is None and not memory:
            database_file = os.path.join(
                FecDataView.get_provenance_dir_path(), PROVENANCE_DB)
        self._database_file = database_file
        SQLiteDB.__init__(self, database_file, ddl_file=_DDL_FILE)

    def insert_power(self, description, the_value):
        """
        Inserts a general power value into the power_provenane table

        :param str description: Type of value
        :param float the_value: data
        """
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO power_provenance(
                    description, the_value)
                VALUES(?, ?)
                """, [description, the_value])

    def insert_other(self, category, description, the_value):
        """
        Insert unforeseen provenance into the other_provenace_table

        This allows to add provenance that does not readily fit into any of
        the other categerogies

        :param str category: grouping from this provenance
        :param str description: Specific provenance being saved
        :param ste the_value: Data
        """
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO other_provenance(
                    category, description, the_value)
                VALUES(?, ?, ?)
                """, [category, description, the_value])

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
        with self.transaction() as cur:
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
        with self.transaction() as cur:
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
        with self.transaction() as cur:
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
        with self.transaction() as cur:
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
        with self.transaction() as cur:
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
        with self.transaction() as cur:
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
            logger.warning(f"Additional interesting provenace items in "
                           f"{self._database_file}")

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
        with self.transaction() as cur:
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
        with self.transaction() as cursor:
            cursor.executemany(
                """
                INSERT OR IGNORE INTO boards_provenance(
                ethernet_x, ethernet_y, ip_addres)
                VALUES (?, ?, ?)
                """, ((x, y, ipaddress)
                      for ((x, y), ipaddress) in connections.items()))

    def _test_log_locked(self, text):
        """
        THIS IS A TESTING METHOD.

        This will lock the database and then try to do a log
        """
        with self.transaction() as cur:
            # lock the database
            cur.execute(
                """
                INSERT INTO reports(message)
                VALUES(?)
                """, [text])
            cur.lastrowid
            # try logging and storing while locked.
            logger.warning(text)
