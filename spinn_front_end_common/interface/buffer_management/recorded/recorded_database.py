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


_DDL_FILE = os.path.join(os.path.dirname(__file__), "recorded_database.sql")
RAW = "_raw"
FULL = "_full"
SIMPLE = "_simple"
AS_FLOAT = "_as_float"
KEYS = "_keys"
MATRIX = "matrix"
EXISTS = "exists"
TYPE_ERROR = "{} {} has already been save as {} so can not save it as {}"


class RecordedDatabase(object):
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

    def _table_name(
            self, source_name, variable_name, postfix, first_id=None):
        """
        Creates a table name based on the parameters

        :param str source_name: The global name for the source.
            (ApplicationVertex name)
        :param str variable_name: The name for the variable being stored
        :param str postfix: Extra to add on to the end
        :param first_id: first id for this core
        :type first_id: str or None
        :return: name for this table/view
        """
        name = source_name + "_" + variable_name + "_"
        if first_id is None:
            return name + "ALL" + postfix
        return name + str(first_id) + postfix

    def _drop_views(self, cursor, source_name, variable_name):
        """
        Drops all views associated this source and variable pair

        :param ~sqlite3.Cursor cursor:
        :param str source_name: The global name for the source.
            (ApplicationVertex name)
        :param str variable_name: The name for the variable being stored
        :return:
        """
        cursor.execute(
                """
                DELETE FROM global_metadata
                WHERE source_name = ? AND variable_name = ?
                """, (source_name, variable_name))
        if cursor.rowcount == 0:
            # No views to drop
            return
        cursor.execute("DROP TABLE IF EXISTS " +
                       self._table_name(source_name, variable_name, SIMPLE))
        cursor.execute("DROP VIEW IF EXISTS " +
                       self._table_name(source_name, variable_name, KEYS))
        cursor.execute("DROP VIEW IF EXISTS " +
                       self._table_name(source_name, variable_name, FULL))
        cursor.execute("DROP VIEW IF EXISTS " +
                       self._table_name(source_name, variable_name, AS_FLOAT))

    def _check_previous_data_type(
            self, cursor, source_name, variable_name, data_type):
        """
        Check that no existing table for this data has a different type

        :param ~sqlite3.Cursor cursor:
        :param str source_name: The global name for the source.
            (ApplicationVertex name)
        :param str variable_name: The name for the variable being stored
        :param str data_type: Tyoe of data for this source_name and
            variable_name pair
        """
        for row in cursor.execute(
                """
                SELECT data_type
                FROM local_metadata
                WHERE source_name = ? AND variable_name = ?
                """, (source_name, variable_name)):
            if row["data_type"] != data_type:
                msg = TYPE_ERROR.format(
                    source_name, variable_name, row["data_type"], data_type)
                raise Exception(msg)

    def _create_matrix_table(
            self, cursor, source_name, variable_name, key, atom_ids):
        """
        Creates a matrix table to hold data from one core.

        :param ~sqlite3.Cursor cursor:
        :param str source_name: The global name for the source.
            (ApplicationVertex name)
        :param str variable_name: The name for the variable being stored
        :param str key: name of the key column
        :param list atom_ids: The ids for this core. Many be integers
        :return: Name of the database table created for this data
        """
        table_name = self._table_name(
            source_name, variable_name, RAW, atom_ids[0])
        neuron_ids_str = ",".join(["'" + str(id) + "'" for id in atom_ids])
        cursor.execute(
            """
            INSERT INTO local_metadata(
                source_name, variable_name, table_name, first_neuron_id,
                data_type)
            VALUES(?,?,?,?,?)
            """, (source_name, variable_name, table_name, atom_ids[0], MATRIX))

        ddl_statement = "CREATE TABLE {} ({}, {})".format(
            table_name, key, neuron_ids_str)
        cursor.execute(ddl_statement)
        return table_name

    def _create_exists_table(
            self, cursor, source_name, variable_name, key):
        """
        Creates an exists table to hold data from all cores.

        :param ~sqlite3.Cursor cursor:
        :param str source_name: The global name for the source.
            (ApplicationVertex name)
        :param str variable_name: The name for the variable being stored
        :param str key: name of the key column
        :return: Name of the database table created for this data
        """
        table_name = self._table_name(source_name, variable_name, RAW)
        cursor.execute(
            """
            INSERT INTO local_metadata(
                source_name, variable_name, table_name, first_neuron_id,
                data_type)
            VALUES(?,?,?,?,?)
            """, (source_name, variable_name, table_name, None, EXISTS))

        ddl_statement = "CREATE TABLE {} (atom_id, {})".format(
            table_name, key)
        cursor.execute(ddl_statement)
        return table_name

    def _get_local_table(
            self, cursor, source_name, variable_name, key, data_type,
            atom_ids=None):
        """
        Ensures a table exists to hold data from one core.

        :param ~sqlite3.Cursor cursor:
        :param str source_name: The global name for the source.
            (ApplicationVertex name)
        :param str variable_name: The name for the variable being stored
        :param str key: Name of the key column if there is one
        :param atom_ids: The ids for this core. Many be integers.
            Or None if there is a single table for all cores
        :type atom_ids: list(int) or None
        :return: Name of the database table created for this data
        """
        if atom_ids:
            cursor.execute(
                """
                SELECT table_name, data_type
                FROM local_metadata
                WHERE source_name = ? AND variable_name = ?
                    AND first_neuron_id = ?
                LIMIT 1
                """, (source_name, variable_name, atom_ids[0]))
        else:
            cursor.execute(
                """
                SELECT table_name, data_type
                FROM local_metadata
                WHERE source_name = ? AND variable_name = ?
                    AND first_neuron_id IS NULL
                LIMIT 1
                """, (source_name, variable_name))
        for row in cursor.fetchall():
            if row["data_type"] != data_type:
                msg = TYPE_ERROR.format(
                    source_name, variable_name, row["data_type"], data_type)
                raise Exception(msg)
            return row["table_name"]

        self._check_previous_data_type(
            cursor, source_name, variable_name, data_type)
        if data_type == MATRIX:
            return self._create_matrix_table(
                cursor, source_name, variable_name, key, atom_ids)
        if data_type == EXISTS:
            return self._create_exists_table(
                cursor, source_name, variable_name, key)

        raise Exception("Unexpected table data_type {}".format(data_type))

    def _count(self, cursor, table_name):
        """
        Counts the rows in a table

        :param ~sqlite3.Cursor cursor:
        :param str table_name:
        :return: The number of rows in the table
        :rtype int
        """
        for row in cursor.execute(
                "SELECT COUNT(*) AS count FROM " + table_name):
            return row["count"]

    def _count_keys(self, cursor, key, table_name):
        """
        Counts the min key, max key and count of the rows in a table

        :param ~sqlite3.Cursor cursor:
        :param str table_name:
        :return: The number of rows in the table
        :rtype int, int, int
        """
        for row in cursor.execute(
                """
                    SELECT MIN({0}) AS min, MAX({0}) as max, 
                    count(*) as count from ({1})
                    """.format(key, table_name)):
            return row["min"], row["max"], row["count"]

    def _create_matrix_views(
            self, cursor, source_name, variable_name, table_names):
        """
        Creates the required views for this source and variable.

        Always creates a "simple" view which is a natural join of all locals
        Also creates a "keys" view which has the keys in any local

        It then check for missing data (keys) in each local
        and if so creates "full" views which include NULL rows as needed
        If required it creates a "full" view joining all the locals/ views
        so that there is no missing data

        :param ~sqlite3.Cursor cursor:
        :param str source_name: The global name for the source.
            (ApplicationVertex name)
        :param str variable_name: The name for the variable being stored
        :param list(str) table_names: Name of local tables
        """
        all_view = self._table_name(source_name, variable_name, SIMPLE)

        # Find the name of the key column
        cursor.execute("SELECT * FROM {}".format(table_names[0]))
        key = cursor.description[0][0]

        counts = []
        the_min, the_max, count = self._count_keys(cursor, key, table_names[0])
        counts.append(count)
        for table_name in table_names[1:]:
            a_min, a_max, count = self._count_keys(cursor, key, table_name)
            if a_min < the_min:
                the_min = a_min
            if a_max > the_max:
                the_max = a_max
            counts.append(count)
        keys_count = the_max - the_min + 1

        # Create query that list all keys in any of the tables
        # avoid triple quote style as it makes string longer
        keys_query = "(WITH RECURSIVE cnt({0})AS(SELECT {1} UNION ALL " \
                     "SELECT {0}+{2} FROM cnt LIMIT {3})" \
                     "SELECT {0} FROM cnt)".format(
            key, the_min, 1, the_max + 1)

        # Check each table to see if it includes all keys
        best_names = []
        for i, table_name in enumerate(table_names):
            if counts[i] == keys_count:
                best_names.append(table_name)
            else:
                # Data missing so create a view with NULLs
                inner = "(SELECT * FROM {} LEFT JOIN {} USING({}))".format(
                    keys_query, table_name, key)
                best_names.append(inner)

        # Create a view using natural join over the complete data for each
        full_view = self._table_name(source_name, variable_name, FULL)
        ddl_statement = "CREATE VIEW {} AS SELECT * FROM {}".format(
            full_view, " NATURAL JOIN ".join(best_names))
        cursor.execute(ddl_statement)
        return full_view

    def _find_best_source(self, cursor, source_name, variable_name):
        """
        Finds the best source for this source variable pair

        Where there is only one local table returns that.
        Otherwise a suitable view is created

        :param ~sqlite3.Cursor cursor:
        :param str source_name: The global name for the source.
            (ApplicationVertex name)
        :param str variable_name: The name for the variable being stored

        :return: Name of table/view and the data_type
        :rtype str, str
        """

        # Find the tables to include
        table_names = []
        data_type = None
        for row in cursor.execute(
                """
                SELECT table_name, data_type FROM local_metadata
                WHERE source_name = ? AND variable_name = ?
                ORDER BY first_neuron_id
                """, (source_name, variable_name)):
            data_type = row["data_type"]
            table_names.append(row["table_name"])

        if len(table_names) == 1:
            # No views needed use the single raw table
            return table_names[0], data_type

        if data_type == MATRIX:
            return self._create_matrix_views(
                cursor, source_name, variable_name, table_names), data_type
        raise Exception("Unexpected table data_type {}".format(data_type))

    def _get_global_view(self, cursor, source_name, variable_name):
        """
        Ensures a single table or view exists to data for all cores
        with this data

        note: It is assumed that data exists for this source and variable

        :param ~sqlite3.Cursor cursor:
        :param str source_name: The global name for the source.
            (ApplicationVertex name)
        :param str variable_name: The name for the variable being stored
        :return: Name of the database view created for this data
        """
        # Check if a single table / view is already known
        for row in cursor.execute(
                """
                SELECT best_source, data_type FROM global_metadata
                WHERE source_name = ? AND variable_name = ?
                LIMIT 1
                """, (source_name, variable_name)):
            return row["best_source"], row["data_type"]

        # Find the best source and type
        best_source, data_type = self._find_best_source(
            cursor, source_name, variable_name)
        # Save this info
        cursor.execute(
            """
            INSERT INTO global_metadata(
                source_name, variable_name, best_source, data_type)
            VALUES(?, ?, ?, ?)
            """,
            (source_name, variable_name, best_source, data_type))

        # It is currently assumed all matrix data is fixed point
        if data_type == MATRIX:
            # Get the column names
            cursor.execute("SELECT * FROM {} LIMIT 1".format(best_source))
            names = [description[0] for description in cursor.description]

            # Add a view converting fixed point to floats
            fields = names[0]
            for name in names[1:]:
                fields += ", '{0}' / 65536.0 AS '{0}'".format(name)
            float_name = self._table_name(source_name, variable_name, AS_FLOAT)

            ddl_statement = "CREATE VIEW {} AS SELECT {} FROM {}".format(
                float_name, fields, best_source)
            cursor.execute(ddl_statement)

        return best_source, data_type

    def _get_source_id(self, cursor, source_name):
        for row in cursor.execute(
                """
                SELECT source_id
                FROM sources
                WHERE source_name = ?
                LIMIT 1
                """, [source_name]):
            return row["source_id"]

        cursor.execute(
            "INSERT INTO sources(source_name) VALUES(?)", [source_name])
        return cursor.lastrowid

    def register_source(self, source_name, description=None, id_offset=None):
         with self._db:
            cursor = self._db.cursor()
            source_id = self._get_source_id(cursor, source_name)
            if description:
                cursor.execute(
                    "UPDATE sources SET description = ? WHERE SOURCE_NAME = ?",
                    (source_name, description))
            if id_offset:
                cursor.execute(
                    "UPDATE sources SET id_offset = ? WHERE SOURCE_NAME = ?",
                    (source_name, id_offset))

    def insert_matrix_items(
            self, source_name, variable_name, key, atom_ids, data):
        """
        Inserts data for one core for this variable

        This method can be called multiple times for the same
        source_name, variable_name, atom_ids combination and the data will go
        into one table

        The first column of the data is assumed to hold the key
        For each source_name, variable_name, atom_ids triple there should never
        be more than one row with the same key. (Even in different calls)

        The remaining columns will hold the data for each id in atom_ids.
        So the with of the data must be len(atom_ids) + 1

        Clears any views for this source and variable pair
        so that which views are required is recomputed based on the new data

        note: Each atom_id must be unigue
            within all calls with the same source_name, variable_name pair
        Multiple calls can repeat atom_ids as long as the list is identical

        :param str source_name: The global name for the source.
            (ApplicationVertex name)
        :param str variable_name: The name for the variable being stored
        :param str key: The name for the first/key column
        :param list atom_ids: The global ids for this core. Many be integers
        :param iterable(iterable) data: The values to load
        :return: Name of the database table created for this data
        """
        with self._db:
            cursor = self._db.cursor()
            self._drop_views(cursor, source_name, variable_name)
            table_name = self._get_local_table(
                cursor, source_name, variable_name, key, MATRIX, atom_ids)
            # Get the column names
            cursor.execute("SELECT * FROM {} LIMIT 1".format(table_name))
            query = "INSERT INTO {} VALUES ({})".format(
                table_name, ",".join("?" for _ in cursor.description))
            cursor.executemany(query, data)

    def insert_exists_items(
            self, source_name, variable_name, key, data):
        """
        Inserts data for one core for this variable

        This method can be called multiple times for the same
        source_name, variable_name, atom_ids combination and the data will go
        into one table

        The first column of the data is assumed to hold the atom_id
        The second column of the data is assumed to hold the key.
        Each row in the data should have exactly two elements.
        There can be multiple rows with the same atom_id and key values

        :param str source_name: The global name for the source.
            (ApplicationVertex name)
        :param str variable_name: The name for the variable being stored
        :param str key: The name for the values in the second/key column
        :param iterable(iterable) data: The values to load
        """
        with self._db:
            cursor = self._db.cursor()
            self._drop_views(cursor, source_name, variable_name)
            table_name = self._get_local_table(
                cursor, source_name, variable_name, key, EXISTS)
            # Get the column names
            cursor.execute("SELECT * FROM {}".format(table_name))
            query = "INSERT INTO {} VALUES ({})".format(
                table_name, ",".join("?" for _ in cursor.description))
            cursor.executemany(query, data)

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

    def create_all_views(self):
        """
        Creates views for all the source / variable pairs

        Can safely be called more than once and a second call will add new
        source/ variable pairs but not update already existing ones

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

        :param str source_name: The global name for the source.
            (ApplicationVertex name)
        :param str variable_name: The name for the variable being stored
        :return: List of column names (key + atom ids) and
            all the data with a key as the first column
        :rtype: tuple(list, list(list(int))
        """
        with self._db:
            cursor = self._db.cursor()
            best_source, data_type = self._get_global_view(
                cursor, source_name, variable_name)
            cursor.execute("SELECT * FROM {}".format(best_source))
            names = [description[0] for description in cursor.description]
            data = [list(row) for row in cursor.fetchall()]
            return names, data

        raise NotImplementedError("Unexpected data_type {}.format(data_type)")

    def get_views(self):
        """
        Gets a list of the currently created views.

        :return: list of the names of all views in the database
        """
        with self._db:
            cursor = self._db.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
            return cursor.fetchall()
