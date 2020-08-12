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

from collections import defaultdict
import os
import sqlite3


_DDL_FILE = os.path.join(os.path.dirname(__file__), "matrix_database.sql")


class MatrixDatabase(object):
    """ Specific implementation of the Database for SQLite 3.

    .. note::
        NOT THREAD SAFE ON THE SAME DB.
        Threads can access different DBs just fine.

    .. note::
        This totally relies on the way SQLite's type affinities function.
        You can't port to a different database engine without a lot of work.
    """

    __slots__ = [
        # the database holding the data to store
        "_db",
    ]

    META_TABLES = ["global_metadata", "local_metadata"]

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
        with open(_DDL_FILE) as f:
            sql = f.read()
        self._db.executescript(sql)

    def _get_local_table(self, cursor, source_name, variable_name, neuron_ids):
        """
        Ensures a table exists to hold data from one core.

        note: It is assumed that the neuron_ids for one core/variable remains
        constants and no not overlap with any other cores with for the same
        source and variable pair

        :param ~sqlite3.Cursor cursor:
        :param str source_name: The global name for the source.
            (ApplicationVertex name)
        :param str variable_name: The name for the variable being stored
        :param list neuron_ids: The ids for this core. Many be integers
        :return: Name of the database table created for this data
        """
        for row in cursor.execute(
                """
                SELECT table_name
                FROM local_metadata
                WHERE source_name = ? AND variable_name = ? 
                    AND first_neuron_id = ?
                LIMIT 1
                """, (source_name, variable_name, neuron_ids[0])):
            return row["table_name"]

        table_name = source_name + "_" + variable_name + "_" + \
                     str(neuron_ids[0])
        neuron_ids_str = ",".join(["'" + str(id) + "'" for id in neuron_ids])
        cursor.execute(
            """
            INSERT INTO local_metadata(
                source_name, variable_name, table_name, first_neuron_id) 
            VALUES(?,?,?,?)
            """, (source_name, variable_name, table_name, neuron_ids[0]))

        ddl_statement = "CREATE TABLE {} (timestamp, {})".format(
            table_name, neuron_ids_str)
        cursor.execute(ddl_statement)
        return table_name

    def _get_global_view(self, cursor, source_name, variable_name):
        """
        Ensures a view exists to data for all cores with this data

        note: It is assumed that this is only called after all cores have
            inserted data at least once.

        :param ~sqlite3.Cursor cursor:
        :param str source_name: The global name for the source.
            (ApplicationVertex name)
        :param str variable_name: The name for the variable being stored
        :return: Name of the database view created for this data
        """
        for row in cursor.execute(
                """
                SELECT view_name FROM global_metadata
                WHERE source_name = ? AND variable_name = ?
                LIMIT 1
                """, (source_name, variable_name)):
            return row["view_name"]

        table_names = []
        for row in cursor.execute(
                """
                SELECT table_name FROM local_metadata
                WHERE source_name = ? AND variable_name = ?
                ORDER BY first_neuron_id
                """, (source_name, variable_name)):
            table_names.append(row["table_name"])

        view_name = source_name + "_" + variable_name
        ddl_statement = "CREATE VIEW {} AS SELECT * FROM {}".format(
            view_name, " NATURAL JOIN ".join(table_names))
        cursor.execute(ddl_statement)
        cursor.execute(
            """
            INSERT INTO global_metadata(
                source_name, variable_name, view_name) 
            VALUES(?,?,?)
            """,
            (source_name, variable_name, view_name))

        cursor.execute("SELECT * FROM {}".format(view_name))
        names = [description[0] for description in cursor.description]

        fields = names[0]
        for name in names[1:]:
            fields += ", '{0}' / 65536.0 AS '{0}'".format(name)
        ddl_statement = "CREATE VIEW {} AS SELECT {} FROM {}".format(
            view_name+"_as_float", fields, view_name)
        cursor.execute(ddl_statement)

        return view_name

    def insert_items(self, source_name, variable_name, neuron_ids, data):
        """
        Inserts data for one core for this variable

        The first column of the data is assumed to hold timestamps
        the rest data for each of the ids in neuron_ids

        note: Many be called more than once for the same core/variable as
        long as the timestamps are unigue

        note: It is assumed that the neuron_ids for one core/variable remains
        constants and no not overlap with any other cores with for the same
        source and variable pair

        :param str source_name: The global name for the source.
            (ApplicationVertex name)
        :param str variable_name: The name for the variable being stored
        :param list neuron_ids: The ids for this core. Many be integers
        :param iterable(iterable) data: The values to load
        :return: Name of the database table created for this data
        """
        with self._db:
            cursor = self._db.cursor()
            table_name = self._get_local_table(
                cursor, source_name, variable_name, neuron_ids)
            cursor.execute("SELECT * FROM {}".format(table_name))
            query = "INSERT INTO {} VALUES ({})".format(
                table_name, ",".join("?" for _ in cursor.description))
            cursor.executemany(query, data)

    def clear_ds(self):
        """ Clear all saved data
        """
        with self._db:
            names = [row["name"]
                            for row in self._db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")]
            for name in self.META_TABLES:
                names.remove(name)
            for name in names:
                self._db.execute("DROP TABLE " + name)
            self._db.execute("DELETE FROM local_metadata")
            names = [row["name"]
                            for row in self._db.execute(
                    "SELECT name FROM sqlite_master WHERE type='view'")]
            for name in names:
                self._db.execute("DROP VIEW " + name)
            for name in self.META_TABLES:
                self._db.execute("DELETE FROM " + name)

    def get_variable_map(self):
        """
        Gets a map of all sources and variables stored in the database

        :return: dict of sources names to a list of variable names
        """
        variables = defaultdict(list)
        with self._db:
            for row in self._db.execute(
                    """
                    SELECT source_name, variable_name 
                    FROM local_metadata 
                    GROUP BY source_name, variable_name
                    """):
                variables[row["source_name"]].append(row["variable_name"])
        return variables

    def create_views(self):
        """
        Creates views for all the source / variable pairs

        Can safely be called more than once and a second call will add new
        source/ variable pairs but not update already existing ones

        note: This method assumes that all core with data for a
            source/variable pair have inserted at least once or all not yet.

        """
        variables = self.get_variable_map()
        with self._db:
            cursor = self._db.cursor()
            for source_name, variables in variables.items():
                for variable_name in variables:
                    self._get_global_view(cursor, source_name, variable_name)

    def get_data(self, source_name, variable_name):
        """
        Gets the data for all cores for this source_name, variabkle name

        note: Current implementaion does not handle missing data well

        :param str source_name: The global name for the source.
            (ApplicationVertex name)
        :param str variable_name: The name for the variable being stored
        :return: Fist of colun names (timestamp + nueron ids) and
            all the data with a timestamp as the first column
        :rtype: tuple(list, list(list(int))
        """
        with self._db:
            cursor = self._db.cursor()
            view_name = self._get_global_view(
                cursor, source_name, variable_name)
            cursor.execute("SELECT * FROM {}".format(view_name))
            names = [description[0] for description in cursor.description]
            data = [list(row[:]) for row in cursor.fetchall()]
            return names, data

    def get_views(self):
        """
        Gets a list of the currently created views.

        :return: list of the names of all views in the database
        """
        with self._db:
            cursor = self._db.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
            return cursor.fetchall()