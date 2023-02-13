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
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB

_DDL_FILE = os.path.join(os.path.dirname(__file__),
                         "db.sql")
_SECONDS_TO_MICRO_SECONDS_CONVERSION = 1000
#: Name of the database in the data folder


def _timestamp():
    return int(time.time() * _SECONDS_TO_MICRO_SECONDS_CONVERSION)


class BaseDatabase(SQLiteDB, AbstractContextManager):
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

    __slots__ = ["_database_file"]

    def __init__(self, database_file=None, *, read_only=False,
                 row_factory=sqlite3.Row, text_factory=memoryview):
        """
        :param str database_file:
            The name of a file that contains (or will contain) an SQLite
            database holding the data.
            If omitted the default location will be used.
        """
        if database_file:
            self._database_file = database_file
        else:
            self._database_file = self.default_database_file()
        super().__init__(
            self._database_file, read_only=read_only, row_factory=row_factory,
            text_factory=text_factory, ddl_file=_DDL_FILE)

    @classmethod
    def default_database_file(cls):
        return os.path.join(FecDataView.get_run_dir_path(),
                            f"data{FecDataView.get_reset_str()}.sqlite3")

    def _get_core_id(self, cursor, x, y, p):
        """
        :param ~sqlite3.Cursor cursor:
        :param int x:
        :param int y:
        :param int p:
        :rtype: int
        """
        for row in cursor.execute(
                """
                SELECT core_id FROM core
                WHERE x = ? AND y = ? AND processor = ?
                LIMIT 1
                """, (x, y, p)):
            return row["core_id"]
        cursor.execute(
            """
            INSERT INTO core(x, y, processor) VALUES(?, ?, ?)
            """, (x, y, p))
        return cursor.lastrowid