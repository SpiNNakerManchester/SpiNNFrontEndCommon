# Copyright (c) 2021 The University of Manchester
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
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB
from .provenance_base import ProvenanceBase


class ProvenanceReader(ProvenanceBase):
    """
    Provides a connection to a database containing provenance for the current
    run and some convenience methods for extracting provenance data from it.

    By default this will wrap around the database used to store the
    provenance of the last run. The path is not updated so this reader is
    not effected by a reset or an end.

    The assumption is that the database is in the current provenance format.
    This includes both that DDL statements used to create the database but
    also the underlying database structure (currently sqlite3)

    .. warning::
        This class is only a wrapper around the database file so if the file
        is deleted the class will no longer work.
    """

    __slots__ = ["_global_data_path", "_mapping_data_path"]

    def __init__(self, global_data_path=None, mapping_data_path=None):
        """
        Create a wrapper around the provenance databases.

        The suggested way to call this is *without* the
        parameters, allowing reader to find the correct path.

        :param global_data_path:
            The name of a file that contains an SQLite
            database holding the data for the whole setup to end
            If omitted, the default file path will be used.
        :type global_data_path: str or None
        :param mapping_data_path:
            The name of a file that contains an SQLite
            database holding the data for a single (mapping) run
            If omitted, the default file path will be used.
        :type mapping_data_path: str or None
        """
        self._global_data_path = global_data_path
        self._mapping_data_path = mapping_data_path

    def _run_query(self, data_path, query, params, read_only, use_sqlite_rows):
        """
        Opens a connection to the database, runs a query,
        extracts the results and closes the connection

        The return type depends on the use_sqlite_rows param.
        By default this method returns tuples (lookup by index) but the
        advanced tuple type can be used instead, which supports lookup by name
        used in the query (use ``AS name`` in the query to set).

        This method will not allow queries that change the database unless the
        read_only flag is set to False.

        :param str data_path: Path to database to run query against
        :param str query: The SQL query to be run. May include ``?`` wildcards
        :param ~collections.abc.Iterable(str or int) params:
            The values to replace the ``?`` wildcards with.
            The number and types must match what the query expects
        :param bool read_only: see :py:meth:`get_database_handle`
        :param bool use_sqlite_rows: see :py:meth:`get_database_handle`
        :return: A list possibly empty of tuples/rows
            (one for each row in the database)
            where the number and type of the values corresponds to the where
            statement
        :rtype: list(tuple or ~sqlite3.Row)
        """
        if not os.path.exists(data_path):
            raise Exception(f"no such DB: {data_path}")
        results = []
        with SQLiteDB(data_path, read_only=read_only,
                      row_factory=(sqlite3.Row if use_sqlite_rows else None),
                      text_factory=None) as db:
            with db.transaction() as cur:
                for row in cur.execute(query, params):
                    results.append(row)
        return results

    def run_global_query(
            self, query, params=(), read_only=True, use_sqlite_rows=False):
        """
        Opens a connection to the global database, runs a query,
        extracts the results and closes the connection

        The return type depends on the use_sqlite_rows param.
        By default this method returns tuples (lookup by index) but the
        advanced tuple type can be used instead, which supports lookup by name
        used in the query (use ``AS name`` in the query to set).

        This method will not allow queries that change the database unless the
        read_only flag is set to False.

        .. note::
            This method is mainly provided as a support method for the later
            methods that return specific data. For new IntergationTests
            please add a specific method rather than call this directly.

        :param str query: The SQL query to be run. May include ``?`` wildcards
        :param ~collections.abc.Iterable(str or int) params:
            The values to replace the ``?`` wildcards with.
            The number and types must match what the query expects
        :param bool read_only: see :py:meth:`get_database_handle`
        :param bool use_sqlite_rows: see :py:meth:`get_database_handle`
        :return: A list possibly empty of tuples/rows
            (one for each row in the database)
            where the number and type of the values corresponds to the where
            statement
        :rtype: list(tuple or ~sqlite3.Row)
        """
        if self._global_data_path is None:
            self._global_data_path = self.get_last_global_database_path()
        return self._run_query(self._global_data_path, query, params,
                               read_only, use_sqlite_rows)

    def run_mapping_query(
            self, query, params=(), read_only=True, use_sqlite_rows=False):
        """
        Opens a connection to the mapping database, runs a query,
        extracts the results and closes the connection

        The return type depends on the use_sqlite_rows param.
        By default this method returns tuples (lookup by index) but the
        advanced tuple type can be used instead, which supports lookup by name
        used in the query (use ``AS name`` in the query to set).

        This method will not allow queries that change the database unless the
        read_only flag is set to False.

        .. note::
            This method is mainly provided as a support method for the later
            methods that return specific data. For new IntergationTests
            please add a specific method rather than call this directly.

        :param str query: The SQL query to be run. May include ``?`` wildcards
        :param ~collections.abc.Iterable(str or int) params:
            The values to replace the ``?`` wildcards with.
            The number and types must match what the query expects
        :param bool read_only: see :py:meth:`get_database_handle`
        :param bool use_sqlite_rows: see :py:meth:`get_database_handle`
        :return: A list possibly empty of tuples/rows
            (one for each row in the database)
            where the number and type of the values corresponds to the where
            statement
        :rtype: list(tuple or ~sqlite3.Row)
        """
        if self._mapping_data_path is None:
            self._mapping_data_path = self.get_last_run_database_path()
        return self._run_query(self._mapping_data_path, query, params,
                               read_only, use_sqlite_rows)

    def cores_with_late_spikes(self):
        """
        Gets the x, y, p and count of the cores where late spikes arrived.

        Cores that received spikes but where none were late are *not* included.

        :return: A list hopefully empty of tuples (x, y, p, count) of cores
            where their where late arriving spikes.
        :rtype: list(tuple(int, int, int, int))
        """
        query = """
            SELECT x, y, p, the_value AS "value"
            FROM core_provenance
            WHERE description = 'Number_of_late_spikes'
                AND the_value > 0
            """
        return self.run_mapping_query(query)

    def get_timer_provenance(self, algorithm):
        """
        Gets the timer provenance item(s) from the last run

        :param str algorithm:
            The value to LIKE search for in the algorithm column.
            Can be the full name, or have ``%``  and ``_`` wildcards.
        :return:
            A possibly multiline string with for each row which matches the
            like a line ``algorithm: value``
        :rtype: str
        """
        query = """
            SELECT algorithm, time_taken
            FROM timer_provenance
            WHERE algorithm LIKE ?
            """
        return "\n".join(
            f"{row[0]}: {row[1]}"
            for row in self.run_global_query(query, [algorithm]))

    def get_run_times(self):
        """
        Gets the algorithm running times from the last run. If an algorithm is
        invoked multiple times in the run, its times are summed.

        :return:
            A possibly multiline string with for each row which matches the
            like a line ``description_name: time``. The times are in seconds.
        :rtype: str
        """
        # We know the database actually stores microseconds for durations
        query = """
            SELECT description, SUM(time_taken) / 1000000.0
            FROM timer_provenance
            GROUP BY description
            ORDER BY the_value
            """
        return "\n".join(
            f"{row[0].replace('_', ' ')}: {row[1]} s"
            for row in self.run_mapping_query(query))

    def get_run_time_of_BufferExtractor(self):
        """
        Gets the BufferExtractor provenance item(s) from the last run

        :return:
            A possibly multiline string with for each row which matches the
            like %BufferExtractor description_name: value
        :rtype: str
        """
        return self.get_timer_provenance("%BufferExtractor")

    def get_provenance_for_router(self, x, y):
        """
        Gets the provenance item(s) from the last run relating to a chip

        :param int x:
            The X coordinate of the chip
        :param int y:
            The Y coordinate of the chip
        :return:
            A possibly multiline string with for each row which matches the
            like a line ``description_name: value``
        :rtype: str
        """
        query = """
            SELECT
                description,
                sum(the_value) AS "value"
            FROM router_provenance
            WHERE x = ? AND y = ?
            GROUP BY description
            ORDER BY description
            """
        return "\n".join(
            f"{ row['description'] }: { row['value'] }"
            for row in self.run_mapping_query(query, [int(x), int(y)],
                                              use_sqlite_rows=True))

    def get_cores_with_provenace(self):
        """
        Gets the cores with provenance

        :return: A list tuples (x, y, p)
        :rtype: list(tuple(int, int, int))
        """
        query = """
            SELECT core_name, x, y, p
            FROM core_provenance_view
            group by x, y, p
            """
        return self.run_mapping_query(query)

    def get_router_by_chip(self, description):
        """
        Gets the router values for a specific item

        :param str description:
        :return: list of tuples x, y, value)
        :rtype: lits((int, int float))
        """
        query = """
            SELECT x, y, the_value
            FROM router_provenance
            WHERE description = ?
            """
        data = self.run_mapping_query(query, [description])
        try:
            return data
        except IndexError:
            return None

    def get_monitor_by_chip(self, description):
        """
        Gets the monitor values for a specific item

        :param str description:
        :return: list of tuples x, y, value)
        :rtype: lits((int, int float))
        """
        query = """
            SELECT x, y, the_value
            FROM monitor_provenance
            WHERE description = ?
            """
        data = self.run_mapping_query(query, [description])
        try:
            return data
        except IndexError:
            return None

    def get_category_timer_sum(self, category):
        """
        Get the total runtime for one category of algorithms

        :param  TimerCategory category:
        :return: total off all runtimes with this category
        :rtype: int
        """
        query = """
             SELECT sum(time_taken)
             FROM category_timer_provenance
             WHERE category = ?
             """
        data = self.run_mapping_query(query, [category.category_name])
        try:
            info = data[0][0]
            if info is None:
                return 0
            return info
        except IndexError:
            return 0

    def get_category_timer_sums(self, category):
        """
        Get the runtime for one category of algorithms
        split machine on, machine off

        :param TimerCategory category:
        :return: total on and off time of instances with this category
        :rtype: int
        """
        on = 0
        off = 0
        query = """
             SELECT sum(time_taken), machine_on
             FROM category_timer_provenance
             WHERE category = ?
             GROUP BY machine_on
             """
        try:
            for data in self.run_mapping_query(query, [category.category_name]):
                if data[1]:
                    on = data[0]
                else:
                    off = data[0]
        except IndexError:
            pass
        return on, off

    def get_timer_sum_by_category(self, category):
        """
        Get the total runtime for one category of algorithms

        :param TimerCategory category:
        :return: total off all runtimes with this category
        :rtype: int
        """
        query = """
             SELECT sum(time_taken)
             FROM full_timer_view
             WHERE category = ?
             """
        data = self.run_mapping_query(query, [category.category_name])
        try:
            info = data[0][0]
            if info is None:
                return 0
            return info
        except IndexError:
            return 0

    def get_timer_sum_by_work(self, work):
        """
        Get the total runtime for one work type of algorithms

        :param TimerWork work:
        :return: total off all runtimes with this category
        :rtype: int
        """
        query = """
             SELECT sum(time_taken)
             FROM full_timer_view
             WHERE work = ?
             """
        data = self.run_mapping_query(query, [work.work_name])
        try:
            info = data[0][0]
            if info is None:
                return 0
            return info
        except IndexError:
            return 0

    def get_timer_sum_by_algorithm(self, algorithm):
        """
        Get the total runtime for one algorithm

        :param str algorithm:
        :return: total off all runtimes with this algorithm
        :rtype: int
        """
        query = """
             SELECT sum(time_taken)
             FROM timer_provenance
             WHERE algorithm = ?
             """
        data = self.run_mapping_query(query, [algorithm])
        try:
            info = data[0][0]
            if info is None:
                return 0
            return info
        except IndexError:
            return 0

    def messages(self):
        """
        List all the provenance messages

        :return: all messages logged or not
        :rtype: list(str)
        """
        query = """
             SELECT message
             FROM reports
             """
        return self.run_mapping_query(query, [])

    def retreive_log_messages(self, min_level=0):
        """
        Retrieves all log messages at or above the min_level

        :param int min_level:
        :rtype: list(tuple(int, str))
        """
        query = """
            SELECT message
            FROM p_log_provenance
            WHERE level >= ?
            """
        messages = self.run_global_query(query, [min_level])
        return list(map(lambda x: x[0], messages))

    @staticmethod
    def demo():
        """ A demonstration of how to use this class.

        See also unittests/interface/provenance/test_provenance_database.py
        """
        # This uses the example file in the same directory as this script
        pr = ProvenanceReader(os.path.join(
            os.path.dirname(__file__), "provenance.sqlite3"))
        print("DIRECT QUERY:")
        query = """
            SELECT x, y, the_value
            FROM router_provenance
            WHERE description = 'Local_P2P_Packets'
            """
        results = pr.run_mapping_query(query)
        for row in results:
            print(row)
        print("\nCORES WITH LATE SPIKES:")
        print(pr.cores_with_late_spikes())
        print("\nRUN TIME OF BUFFER EXTRACTOR:")
        print(pr.get_run_time_of_BufferExtractor())
        print("\nROUETER (0,0) PROVENANCE:")
        print(pr.get_provenance_for_router(0, 0))
        print("\nCORES WITH PROVENACE")
        print(pr.get_cores_with_provenace())


if __name__ == '__main__':
    ProvenanceReader.demo()
