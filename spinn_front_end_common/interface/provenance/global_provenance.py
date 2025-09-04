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

from datetime import datetime, timedelta
import logging
import os
import re
from sqlite3 import Row
from typing import Iterable, List, Optional, Tuple, Union

from spinn_utilities.config_holder import get_timestamp_path
from spinn_utilities.log import FormatAdapter

from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.constants import (
    MICRO_TO_MILLISECOND_CONVERSION)
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB
from spinn_front_end_common.interface.provenance.timer_work import TimerWork

from .timer_category import TimerCategory

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

    __slots__ = ("_database_file", )

    @classmethod
    def get_global_provenace_path(cls) -> str:
        """
        Get the path of the current provenance database of the last run

        Used the cfg setting tpath_global_provenance
        placing this in the timestamp directory

        .. warning::
            Calling this method between start/reset and run may result in a
            path to a database not yet created.

        :raises ValueError:
            if the system is in a state where path can't be retrieved,
            for example before run is called
        :returns: Directory for this database based on the cfg setting
        """
        return get_timestamp_path("tpath_global_provenance")

    def __init__(
            self, database_file: Optional[str] = None, memory: bool = False):
        """
        :param database_file:
            The name of a file that contains (or will contain) an SQLite
            database holding the data.
            If omitted, either the default file path or an unshared in-memory
            database will be used (suitable only for testing).
        :param memory:
            Flag to say unshared in-memory can be used.
            Otherwise a `None` file will mean the default should be used
        """
        if database_file is None and not memory:
            database_file = self.get_global_provenace_path()
        self._database_file = database_file
        SQLiteDB.__init__(self, database_file, ddl_file=_DDL_FILE,
                          row_factory=None, text_factory=None)

    def insert_version(self, description: str, the_value: str) -> None:
        """
        Inserts data into the version_provenance table

        :param description: The package for which the version applies
        :param the_value: The version to be recorded
        """
        self.cursor().execute(
            """
            INSERT INTO version_provenance(
                description, the_value)
            VALUES(?, ?)
            """, [description, the_value])

    def insert_run_reset_mapping(self) -> None:
        """
        Inserts a mapping between rest number and run number
        """
        self.cursor().execute(
            """
            INSERT INTO run_reset_mapping(
                n_run, n_reset)
            VALUES(?, ?)
            """,
            [FecDataView.get_run_number(), FecDataView.get_reset_number()])

    def insert_category(
            self, category: TimerCategory, machine_on: bool) -> int:
        """
        Inserts category into the category_timer_provenance  returning id

        :param category: Name of Category starting
        :param machine_on: If the machine was done during all
            or some of the time
        :returns: ID of the inserted category
        """
        self.cursor().execute(
            """
            INSERT INTO category_timer_provenance(
                category, machine_on, n_run, n_loop)
            VALUES(?, ?, ?, ?)
            """,
            [category.category_name, machine_on,
             FecDataView.get_run_number(),
             FecDataView.get_run_step()])
        return self.lastrowid

    def insert_category_timing(
            self, category_id: int, delta: timedelta) -> None:
        """
        Inserts run time into the category

        :param category_id: id of the Category finished
        :param delta: Time to be recorded
       """
        time_taken = (
                (delta.seconds * MICRO_TO_MILLISECOND_CONVERSION) +
                (delta.microseconds / MICRO_TO_MILLISECOND_CONVERSION))

        self.cursor().execute(
            """
            UPDATE category_timer_provenance
            SET
                time_taken = ?
            WHERE category_id = ?
            """, (time_taken, category_id))

    def insert_timing(
            self, category: int, algorithm: str, work: TimerWork,
            delta: timedelta, skip_reason: Optional[str]) -> None:
        """
        Inserts algorithms run times into the timer_provenance table

        :param category: Category Id of the Algorithm
        :param algorithm: Algorithm name
        :param work: Type of work being done
        :param delta: Time to be recorded
        :param skip_reason: The reason the algorithm was skipped or `None` if
            it was not skipped
        """
        time_taken = (
                (delta.seconds * MICRO_TO_MILLISECOND_CONVERSION) +
                (delta.microseconds / MICRO_TO_MILLISECOND_CONVERSION))
        self.cursor().execute(
            """
            INSERT INTO timer_provenance(
                category_id, algorithm, work, time_taken, skip_reason)
            VALUES(?, ?, ?, ?, ?)
            """,
            [category, algorithm, work.work_name, time_taken, skip_reason])

    def store_log(self, level: int, message: str,
                  timestamp: Optional[datetime] = None) -> None:
        """
        Stores log messages into the database
        """
        if timestamp is None:
            timestamp = datetime.now()
        self.cursor().execute(
            """
            INSERT INTO p_log_provenance(
                timestamp, level, message)
            VALUES(?, ?, ?)
            """,
            [timestamp, level, message])

    def _test_log_locked(self, text: str) -> None:
        """
        THIS IS A TESTING METHOD.

        This will lock the database and then try to do a log
        """
        # lock the database
        self.cursor().execute(
            """
            INSERT INTO version_provenance(
                description, the_value)
            VALUES("foo", "bar")
            """)
        # try logging and storing while locked.
        logger.warning(text)

    def run_query(self, query: str,
                  params: Iterable[Union[str, int, float, None, bytes]] = ()
                  ) -> List[Row]:
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

        :param query: The SQL query to be run. May include ``?`` wildcards
        :param params:
            The values to replace the ``?`` wildcards with.
            The number and types must match what the query expects
        :return: A list possibly empty of tuples/rows
            (one for each row in the database)
            where the number and type of the values corresponds to the where
            statement
        """
        results = []
        for row in self.cursor().execute(query, list(params)):
            results.append(row)
        return results

    def get_timer_provenance(self, algorithm: str) -> str:
        """
        Gets the timer provenance item(s) from the last run

        :param algorithm:
            The value to LIKE search for in the algorithm column.
            Can be the full name, or have ``%``  and ``_`` wildcards.
        :return:
            A possibly multi line string with for each row which matches the
            like a line ``algorithm: value``
        """
        query = """
            SELECT algorithm, time_taken
            FROM timer_provenance
            WHERE algorithm LIKE ?
            """
        return "\n".join(
            f"{row[0]}: {row[1]}"
            for row in self.run_query(query, [algorithm]))

    def get_run_times(self) -> str:
        """
        Gets the algorithm running times from the last run. If an algorithm is
        invoked multiple times in the run, its times are summed.

        :return:
            A possibly multi line string with for each row which matches the
            like a line ``description_name: time``. The times are in seconds.
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

    def get_run_time_of_buffer_extractor(self) -> str:
        """
        Gets the buffer extractor provenance item(s) from the last run

        :return:
            A possibly multi line string with for each row which matches the
            ``LIKE %BufferExtractor``
        """
        return self.get_timer_provenance("%BufferExtractor")

    def get_category_timer_sum(self, category: TimerCategory) -> int:
        """
        Get the total runtime for one category of algorithms

        :param category:
        :return: total off all run times with this category
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

    def get_category_timer_sum_by_reset(self, category: TimerCategory,
                                        n_reset: Optional[int] = None) -> int:
        """
        Get the total runtime for one category of algorithms

        :return: total off all run times with this category
        """
        if n_reset is None:
            n_reset = FecDataView.get_reset_number()
        query = """
             SELECT sum(time_taken)
             FROM category_timer_view
             WHERE category = ? AND n_reset = ?
             """
        data = self.run_query(query, [category.category_name, n_reset])
        try:
            info = data[0][0]
            if info is None:
                return 0
            return info
        except IndexError:
            return 0

    def get_category_timer_sums(
            self, category: TimerCategory) -> Tuple[int, int]:
        """
        Get the runtime for one category of algorithms
        split machine on, machine off

        :param category:
        :return: total on and off time of instances with this category
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

    def get_timer_sum_by_category(self, category: TimerCategory) -> int:
        """
        Get the total runtime for one category of algorithms

        :param category:
        :return: total of all run times with this category
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

    def get_timer_sum_by_category_and_reset(
            self, category: TimerCategory,
            n_reset: Optional[int] = None) -> int:
        """
        Get the total runtime for one category of algorithms

        :return: total of all run times with this category
        """
        if n_reset is None:
            n_reset = FecDataView.get_reset_number()
        query = """
             SELECT sum(time_taken)
             FROM full_timer_view
             WHERE category = ? AND n_reset = ?
             """
        data = self.run_query(query, [category.category_name, n_reset])
        try:
            info = data[0][0]
            if info is None:
                return 0
            return info
        except IndexError:
            return 0

    def get_timer_sum_by_work(self, work: TimerWork) -> int:
        """
        Get the total runtime for one work type of algorithms

        :param work:
        :return: total off all run times with this category
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

    def get_timer_sum_by_algorithm(self, algorithm: str) -> int:
        """
        Get the total runtime for one algorithm

        :param algorithm:
        :return: total off all run times with this algorithm
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

    def retreive_log_messages(
            self, min_level: int = 0) -> List[str]:
        """
        :returns: All log messages at or above the min_level
        """
        query = """
            SELECT message
            FROM p_log_provenance
            WHERE level >= ?
            """
        messages = self.run_query(query, [min_level])
        return list(map(lambda x: x[0], messages))
