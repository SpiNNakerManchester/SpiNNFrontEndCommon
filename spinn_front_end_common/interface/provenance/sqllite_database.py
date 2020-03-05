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
import os
import sqlite3
import sys


if sys.version_info < (3,):
    # pylint: disable=redefined-builtin, undefined-variable
    memoryview = buffer  # noqa

_DDL_FILE = os.path.join(os.path.dirname(__file__), "db.sql")


class SqlLiteDatabase(object):
    """ Specific implementation of the Database for SQLite 3.

    .. note::
        NOT THREAD SAFE ON THE SAME DB. \
        Threads can access different DBs just fine.
    """

    __slots__ = [
        # the database holding the data to store
        "_db",
    ]

    def __init__(self, database_file=None):
        """
        :param database_file: The name of a file that contains (or will\
            contain) an SQLite database holding the data. If omitted, an\
            unshared in-memory database will be used.
        :type database_file: str
        """
        if database_file is None:
            database_file = ":memory:"  # Magic name!
        self._db = sqlite3.connect(database_file)
        self.__init_db()

    def __del__(self):
        self.close()

    def __enter__(self):
        """ Start mehod is use in a with statement
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        End method if used in a with statement
        :param exc_type:
        :param exc_val:
        :param exc_tb:
        :return:
        """
        self.close()

    def close(self):
        if self._db is not None:
            self._db.close()
            self._db = None

    def __init_db(self):
        """ Set up the database if required. """
        self._db.row_factory = sqlite3.Row
        self._db.text_factory = memoryview
        with open(_DDL_FILE) as f:
            sql = f.read()
        self._db.executescript(sql)

    def insert_items(self, items):
        with self._db:
            self._db.executemany(
                "INSERT OR IGNORE INTO source(source_name) VALUES(?)",
                ((s,) for s in set(item.names[0] for item in items)))
            self._db.executemany(
                "INSERT OR IGNORE INTO description(description_name) VALUES(?)",
                ((d,) for d in set(item.names[-1] for item in items)))
            self._db.executemany(
                "INSERT INTO provenance(source_id, description_id, the_value) "
                "VALUES((SELECT source_id FROM source WHERE source_name = ?), "
                "(SELECT description_id FROM description "
                "WHERE description_name = ?), ?)",
                (self.__condition_row(item) for item in items))

    @staticmethod
    def __condition_row(item):
        value = item.value
        if isinstance(value, datetime.timedelta):
            value = value.microseconds
        return item.names[0], item.names[-1], value

    def insert_item(self, item):
        with self._db:
            cursor = self._db.cursor()
            source_id = self.__get_source_id(cursor, item.names[0])
            description_id = self.__get_description_id(cursor, item.names[-1])
            value = item.value
            if isinstance(value, datetime.timedelta):
                value = value.microseconds
            cursor.execute(
                "INSERT INTO provenance(source_id, description_id, the_value) "
                "VALUES(?, ?, ?)",
                (source_id, description_id, str(value)))

    def __get_source_id(self, cursor, source_name):
        for row in cursor.execute(
                "SELECT source_id FROM source "
                + "WHERE source_name = ? ",
                (source_name, )):
            return row["source_id"]
        cursor.execute(
            "INSERT INTO source(source_name) VALUES(?)",
            (source_name, ))
        return cursor.lastrowid

    def __get_description_id(self, cursor, description_name):
        for row in cursor.execute(
                "SELECT description_id FROM description "
                + "WHERE description_name = ? ",
                (description_name, )):
            return row["description_id"]
        cursor.execute(
            "INSERT INTO description(description_name) VALUES(?)",
            (description_name, ))
        return cursor.lastrowid
