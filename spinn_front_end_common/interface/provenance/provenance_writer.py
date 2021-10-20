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

import datetime
import logging
import os
import re
from spinn_utilities.config_holder import get_config_int
from spinn_utilities.log import FormatAdapter
from spinn_utilities.ordered_set import OrderedSet
from spinn_front_end_common.utilities import globals_variables
from spinn_front_end_common.utilities.constants import PROVENANCE_DB
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB

logger = FormatAdapter(logging.getLogger(__name__))

_DDL_FILE = os.path.join(os.path.dirname(__file__), "db.sql")
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
                globals_variables.provenance_file_path(), PROVENANCE_DB)
        self._database_file = database_file
        super().__init__(database_file, ddl_file=_DDL_FILE)

    def insert_version(self, description, the_value, message=None):
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO version_provenance(
                    description, the_value)
                VALUES(?, ?)
                """, [description, the_value])
        self.insert_report(message)

    def insert_power(self, description, the_value, message=None):
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO power_provenance(
                    description, the_value)
                VALUES(?, ?)
                """, [description, the_value])
        self.insert_report(message)

    def insert_timing(self, category, algorithm, the_value, message=None):
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO timer_provenance(
                    category, algorithm, the_value)
                VALUES(?, ?, ?)
                """, [category, algorithm, the_value])
        self.insert_report(message)

    def insert_other(self, category, description, the_value, message=None):
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO other_provenance(
                    category, description, the_value)
                VALUES(?, ?, ?)
                """, [category, description, the_value])
        self.insert_report(message)

    def insert_gatherer(self, x, y, address, bytes, run, description,
                        the_value, message=None):
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO gatherer_provenance(
                    x, y, address, bytes, run, description, the_value)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """, [x, y, address, bytes, run, description, the_value])
        self.insert_report(message)

    def insert_monitor(self, x, y, description, the_value, message=None):
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO monitor_provenance(
                    x, y, description, the_value)
                VALUES(?, ?, ?, ?)
                """, [x, y, description, the_value])
        self.insert_report(message)

    def insert_router(
            self, x, y, description, the_value, expected, message=None):
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO router_provenance(
                    x, y, description, the_value, expected)
                VALUES(?, ?, ?, ?, ?)
                """, [x, y, description, the_value, expected])
        self.insert_report(message)

    def insert_core(self, x, y, p, description, the_value, message=None):
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO core_provenance(
                    x, y, p, description, the_value)
                VALUES(?, ?, ?, ?, ?)
                """, [x, y, p, description, the_value])
        self.insert_report(message)

    def add_core_name(self, x, y, p, core_name):
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT OR IGNORE INTO core_mapping(
                    x, y, p, core_name)
                VALUES(?, ?, ?, ?) 
                """, [x, y, p, core_name])

    def insert_report(self, message=None):
        if not message:
            return
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
            the_value, message=None):
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT OR IGNORE INTO connector_provenance(
                    pre_population, post_population, the_type, description, the_value)
                VALUES(?, ?, ?, ?, ?) 
                """, [pre_population, post_population, the_type, description, the_value])
        self.insert_report(message)
