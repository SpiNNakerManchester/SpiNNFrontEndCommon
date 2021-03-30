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
import re
from spinn_utilities.ordered_set import OrderedSet
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB

_DDL_FILE = os.path.join(os.path.dirname(__file__), "db.sql")
_RE = re.compile(r"(\d+)([_,:])(\d+)(?:\2(\d+))?")


class SqlLiteDatabase(SQLiteDB):
    """ Specific implementation of the Database for SQLite 3.

    .. note::
        *Not thread safe on the same database file.*
        Threads can access different DBs just fine.

    .. note::
        This totally relies on the way SQLite's type affinities function.
        You can't port to a different database engine without a lot of work.
    """

    __slots__ = []

    def __init__(self, database_file=None):
        """
        :param str database_file:
            The name of a file that contains (or will contain) an SQLite
            database holding the data. If omitted, an unshared in-memory
            database will be used (suitable only for testing).
        :type database_file: str
        """
        super().__init__(database_file, ddl_file=_DDL_FILE)

    def insert_items(self, items):
        """ Does a bulk insert of the items into the database.

        :param list(ProvenanceDataItem) items: The items to insert
        """
        with self.transaction() as cur:
            cur.executemany(
                """
                INSERT OR IGNORE INTO source(
                    source_name, source_short_name, x, y, p)
                VALUES(?, ?, ?, ?, ?)
                """, self.__unique_sources(items, slice(None, -1), "/"))
            cur.executemany(
                """
                INSERT OR IGNORE INTO description(description_name)
                VALUES(?)
                """, self.__unique_names(items, -1))
            cur.executemany(
                """
                INSERT INTO provenance(
                    source_id, description_id, the_value)
                VALUES((
                    SELECT source_id FROM source WHERE source_name = ?
                ), (
                    SELECT description_id FROM description
                    WHERE description_name = ?
                ), ?)
                """, map(self.__condition_row, items))

    @classmethod
    def __unique_names(cls, items, index):
        """ Produces an iterable of 1-tuples of the *unique* names in at \
            particular index into the provenance items' names.

        :param iterable(ProvenanceDataItem) items: The prov items
        :param int index: The index into the names
        :rtype: iterable(tuple(str))
        """
        return ((name,) for name in OrderedSet(
            item.names[index] for item in items))

    @classmethod
    def __unique_sources(cls, items, index, joiner):
        """ Produces an iterable of 1-tuples of the *unique* names in at \
            particular index into the provenance items' names.

        :param iterable(ProvenanceDataItem) items: The prov items
        :param index: The index into the names
        :type index: int or slice
        :param str joiner: Used to make compound names when slices are used
        :rtype: iterable(tuple(str,str,int or None,int or None,int or None))
        """
        if isinstance(index, int):
            return (cls.__coordify(name) for name in OrderedSet(
                item.names[index] for item in items))
        return (cls.__coordify(name, joiner) for name in OrderedSet(
            joiner.join(item.names[index]) for item in items))

    @staticmethod
    def __coordify(name, joiner=None):
        """ Creates the tuple of values for insertion into the source table.

        :param str name: The extracted, possibly compound name
        :rtype: tuple(str, str, int or None, int or None, int or None)
        """
        x = None
        y = None
        p = None
        short_name = name.split(joiner, 1)[0]
        match = _RE.search(name)
        if match:
            x = int(match.group(1))
            y = int(match.group(3))
            if match.group(4):
                p = int(match.group(4))
        return (name, short_name, x, y, p)

    @staticmethod
    def __condition_row(item, joiner="/"):
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
        return joiner.join(item.names[:-1]), item.names[-1], value
