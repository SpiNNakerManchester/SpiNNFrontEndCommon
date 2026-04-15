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

import os
import sqlite3
import time
from typing import Optional, Union
from typing_extensions import TypeAlias

from spinn_utilities.config_holder import get_report_path

from spinn_front_end_common.utilities.sqlite_db import SQLiteDB

_DDL_FILE = os.path.join(os.path.dirname(__file__),
                         "db.sql")
_SECONDS_TO_MICRO_SECONDS_CONVERSION = 1000
_SqliteTypes: TypeAlias = Union[str, int, float, bytes, None]


def _timestamp() -> int:
    return int(time.time() * _SECONDS_TO_MICRO_SECONDS_CONVERSION)


class BaseDatabase(SQLiteDB):
    """
    Specific implementation of the Database for SQLite 3.

    There should only ever be a single Database Object in use at any time.
    In the case of application_graph_changed the first should closed and
    a new one created.

    If 2 database objects where opened with the database_file they hold the
    same data. Unless someone else deletes that file.

    .. note::
        *Not thread safe on the same database file!*
        Threads can access different DBs just fine.
    """

    __slots__ = ("_database_file", )

    def __init__(self, database_file: Optional[str] = None, *,
                 read_only: bool = False,
                 row_factory: Optional[type] = sqlite3.Row,
                 text_factory: Optional[type] = memoryview):
        """
        :param database_file:
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
    def default_database_file(cls) -> str:
        """
        The path to the stand place the data.sqlite3 file will be stored

        This will be based on the cfg setting path_data_database
        and the report directory for the current run.

        There is no guarantee that the database has already been created.

        :returns: The path to the database file
        """
        return get_report_path("path_data_database")

    def _get_core_id(
            self, x: int, y: int, p: int) -> int:
        """
        Get the ID for a core.
        """
        for row in self.cursor().execute(
                """
                SELECT core_id FROM core
                WHERE x = ? AND y = ? AND processor = ?
                LIMIT 1
                """, (x, y, p)):
            return row["core_id"]
        self.cursor().execute(
            """
            INSERT INTO core(x, y, processor) VALUES(?, ?, ?)
            """, (x, y, p))
        return self.lastrowid
