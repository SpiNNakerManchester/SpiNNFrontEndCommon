# Copyright (c) 2017 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from datetime import datetime
import logging
import os
import re
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.constants import (
    MICRO_TO_MILLISECOND_CONVERSION)
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB

logger = FormatAdapter(logging.getLogger(__name__))

_DDL_FILE = os.path.join(os.path.dirname(__file__), "global.sql")
_RE = re.compile(r"(\d+)([_,:])(\d+)(?:\2(\d+))?")


class GlobalProvenance(SQLiteDB):
    """
    Specific implementation of the Database for SQLite 3.

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

    @classmethod
    def get_global_provenace_path(cls):
        """
        Get the path of the current provenance database of the last run

        .. warning::
            Calling this method between start/reset and run may result in a
            path to a database not yet created.

        :raises ValueError:
            if the system is in a state where path can't be retrieved,
            for example before run is called
        """
        return os.path.join(
            FecDataView.get_timestamp_dir_path(),
            "global_provenance.sqlite3")

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
            Otherwise a `None` file will mean the default should be used
        """
        if database_file is None and not memory:
            database_file = self.get_global_provenace_path()
        self._database_file = database_file
        SQLiteDB.__init__(self, database_file, ddl_file=_DDL_FILE,
                          row_factory=None, text_factory=None)

    def insert_version(self, description, the_value):
        """
        Inserts data into the version_provenance table

        :param str description: The package for which the version applies
        :param str the_value: The version to be recorded
        """
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO version_provenance(
                    description, the_value)
                VALUES(?, ?)
                """, [description, the_value])

    def insert_category(self, category, machine_on):
        """
        Inserts category into the category_timer_provenance  returning id

        :param TimerCategory category: Name of Category starting
        :param bool machine_on: If the machine was done during all
            or some of the time
        """
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO category_timer_provenance(
                    category, machine_on, n_run, n_loop)
                VALUES(?, ?, ?, ?)
                """,
                [category.category_name, machine_on,
                 FecDataView.get_run_number(),
                 FecDataView.get_run_step()])
            return cur.lastrowid

    def insert_category_timing(self, category_id, timedelta):
        """
        Inserts run time into the category

        :param int category_id: id of the Category finished
        :param ~datetime.timedelta timedelta: Time to be recorded
       """
        time_taken = (
                (timedelta.seconds * MICRO_TO_MILLISECOND_CONVERSION) +
                (timedelta.microseconds / MICRO_TO_MILLISECOND_CONVERSION))

        with self.transaction() as cur:
            cur.execute(
                """
                UPDATE category_timer_provenance
                SET
                    time_taken = ?
                WHERE category_id = ?
                """, (time_taken, category_id))

    def insert_timing(
            self, category, algorithm, work, timedelta, skip_reason):
        """
        Inserts algorithms run times into the timer_provenance table

        :param int category: Category Id of the Algorithm
        :param str algorithm: Algorithm name
        :param TimerWork work: Type of work being done
        :param ~datetime.timedelta timedelta: Time to be recorded
        :param skip_reason: The reason the algorithm was skipped or `None` if
            it was not skipped
        :type skip_reason: str or None
        """
        time_taken = (
                (timedelta.seconds * MICRO_TO_MILLISECOND_CONVERSION) +
                (timedelta.microseconds / MICRO_TO_MILLISECOND_CONVERSION))
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO timer_provenance(
                    category_id, algorithm, work, time_taken, skip_reason)
                VALUES(?, ?, ?, ?, ?)
                """,
                [category, algorithm, work.work_name, time_taken, skip_reason])

    def store_log(self, level, message, timestamp=None):
        """
        Stores log messages into the database

        :param int level:
        :param str message:
        """
        if timestamp is None:
            timestamp = datetime.now()
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO p_log_provenance(
                    timestamp, level, message)
                VALUES(?, ?, ?)
                """,
                [timestamp, level, message])

    def _test_log_locked(self, text):
        """
        THIS IS A TESTING METHOD.

        This will lock the database and then try to do a log
        """
        with self.transaction() as cur:
            # lock the database
            cur.execute(
                """
                INSERT INTO version_provenance(
                    description, the_value)
                VALUES("foo", "bar")
                """)
            # try logging and storing while locked.
            logger.warning(text)

    def run_query(self, query, params=()):
        """
        Opens a connection to the database, runs a query, extracts the results
        and closes the connection

        The return type depends on the use_sqlite_rows parameter.
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
        results = []
        with self.transaction() as cur:
            for row in cur.execute(query, params):
                results.append(row)
        return results

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
            for row in self.run_query(query, [algorithm]))

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
            for row in self.run_query(query))

    def get_run_time_of_BufferExtractor(self):
        """
        Gets the buffer extractor provenance item(s) from the last run

        :return:
            A possibly multiline string with for each row which matches the
            ``LIKE %BufferExtractor``
        :rtype: str
        """
        return self.get_timer_provenance("%BufferExtractor")

    def get_category_timer_sum(self, category):
        """
        Get the total runtime for one category of algorithms

        :param TimerCategory category:
        :return: total off all run times with this category
        :rtype: int
        """
        query = """
             SELECT sum(time_taken)
             FROM category_timer_provenance
             WHERE category = ?
             """
        data = self.run_query(query, [category.category_name])
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
            for data in self.run_query(query, [category.category_name]):
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
        :return: total off all run times with this category
        :rtype: int
        """
        query = """
             SELECT sum(time_taken)
             FROM full_timer_view
             WHERE category = ?
             """
        data = self.run_query(query, [category.category_name])
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
        data = self.run_query(query, [work.work_name])
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
        data = self.run_query(query, [algorithm])
        try:
            info = data[0][0]
            if info is None:
                return 0
            return info
        except IndexError:
            return 0

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
        messages = self.run_query(query, [min_level])
        return list(map(lambda x: x[0], messages))
