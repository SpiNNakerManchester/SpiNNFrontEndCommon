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
from spinn_utilities.ordered_set import OrderedSet


if sys.version_info < (3,):
    # pylint: disable=redefined-builtin, undefined-variable
    memoryview = buffer  # noqa

_DDL_FILE = os.path.join(os.path.dirname(__file__), "db.sql")


class SqlLiteDatabase(object):
    """ Specific implementation of the Database for SQLite 3.

    .. note::
        NOT THREAD SAFE ON THE SAME DB. \
        Threads can access different DBs just fine.

    .. note::
        This totally relies on the way SQLite's type affinities function.
        You can't port to a different database engine without a lot of work.
    """

    __slots__ = [
        # the database holding the data to store
        "_db",
    ]

    def __init__(self, database_file=None):
        """
        :param str database_file: The name of a file that contains (or will\
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
        """ Start method is use in a ``with`` statement
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """ End method if used in a ``with`` statement.

        :param exc_type:
        :param exc_val:
        :param exc_tb:
        :return:
        """
        self.close()

    def close(self):
        """ Finalises and closes the database.
        """
        if self._db is not None:
            self._db.close()
            self._db = None

    def __init_db(self):
        """ Set up the database if required.
        """
        self._db.row_factory = sqlite3.Row
        self._db.text_factory = memoryview
        with open(_DDL_FILE) as f:
            sql = f.read()
        self._db.executescript(sql)

    def insert_items(self, items):
        """ Does a bulk insert of the items into the database.

        :param list(ProvenanceDataItem) items: The items to insert
        """
        with self._db:
            self._db.executemany(
                "INSERT OR IGNORE INTO source(source_name) VALUES(?)",
                self.__unique_names(items, 0))
            self._db.executemany(
                "INSERT OR IGNORE INTO description(description_name) "
                "VALUES(?)",
                self.__unique_names(items, -1))
            self._db.executemany(
                "INSERT INTO provenance(source_id, description_id, the_value) "
                "VALUES((SELECT source_id FROM source WHERE source_name = ?), "
                "(SELECT description_id FROM description "
                "WHERE description_name = ?), ?)",
                map(self.__condition_row, items))

    @staticmethod
    def __unique_names(items, index):
        """ Produces an iterable of 1-tuples of the *unique* names in at \
            particular index into the provenance items' names.

        :param iterable(ProvenanceDataItem) items: The prov items
        :param int index: The index into the names
        :rtype: iterable(tuple(str))
        """
        return ((name,) for name in OrderedSet(
            item.names[index] for item in items))

    @staticmethod
    def __condition_row(item):
        """ Converts a provenance item into the form ready for insert.

        .. note::
            This totally relies on the way SQLite's type affinities work.
            In particular, we can store any old item type, which is very
            convenient!

        :param ProvenanceDataItem item: The prov item
        :rtype: tuple(str, str, int or float or str)
        """
        value = item.value
        if isinstance(value, datetime.timedelta):
            value = value.microseconds
        return item.names[0], item.names[-1], value
