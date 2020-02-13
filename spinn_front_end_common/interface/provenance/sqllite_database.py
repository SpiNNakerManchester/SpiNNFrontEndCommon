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
import sys
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import AbstractDatabase
from spinn_utilities.overrides import overrides

if sys.version_info < (3,):
    # pylint: disable=redefined-builtin, undefined-variable
    memoryview = buffer  # noqa

_DDL_FILE = os.path.join(os.path.dirname(__file__), "db.sql")


class SqlLiteDatabase(AbstractDatabase):
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

    def insert_item(self, item):
        with self._db:
            cursor = self._db.cursor()
            vertex_id = self.__get_vertex_id(cursor, item.names[0])
            description_id = self.__get_description_id(cursor, item.names[-1])
            cursor.execute(
                "INSERT INTO provenance(vertex_id, description_id, the_value) VALUES(?, ?, ?)",
                (vertex_id, description_id, item.value))

    def __get_vertex_id(self, cursor, vertex_name):
        for row in cursor.execute(
                "SELECT vertex_id FROM vertex "
                + "WHERE vertex_name = ? ",
                (vertex_name, )):
            return row["vertex_id"]
        cursor.execute(
            "INSERT INTO vertex(vertex_name) VALUES(?)",
            (vertex_name, ))
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
