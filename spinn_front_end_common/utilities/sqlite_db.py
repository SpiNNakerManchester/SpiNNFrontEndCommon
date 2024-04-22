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

from __future__ import annotations
import hashlib
import logging
import os
import pathlib
import sqlite3
import struct
from typing import Optional, Type, Union
from pacman.exceptions import PacmanValueError
from spinn_front_end_common.utilities.exceptions import DatabaseException

logger = logging.getLogger(__name__)


class SQLiteDB(object):
    """
    General support class for SQLite databases. This handles a lot of the
    low-level detail of setting up a connection.

    Basic usage (with the default row type)::

        with SQLiteDB("db_file.sqlite3") as database:
            with database.transaction() as cursor:
                for row in cursor.execute("SELECT thing FROM ..."):
                    print(row["thing"])

    This class is designed to be either used as above or by subclassing.
    See the `SQLite SQL documentation <https://www.sqlite.org/lang.html>`_ for
    details of how to write queries, and the Python :py:mod:`sqlite3` module
    for how to do parameter binding.

    .. note::
        If you plan to use the WAL journal mode for the DB, you are
        *recommended* to set this up in the DDL file via::

            PRAGMA journal_mode=WAL;

        This is because the journal mode is persistent for database.
        For details, see the
        `SQLite documentation <https://www.sqlite.org/wal.html>`_ on
        the write-ahead log.
    """

    __slots__ = (
        # the cursor object to use
        "__cursor",
        # the database holding the data to store
        "__db")

    def __init__(
            self, database_file: Optional[str] = None, *,
            read_only: bool = False, ddl_file: Optional[str] = None,
            row_factory: Optional[Union[
                Type[sqlite3.Row], Type[tuple]]] = sqlite3.Row,
            text_factory: Optional[Union[
                Type[memoryview], Type[str]]] = memoryview,
            case_insensitive_like: bool = True, timeout: float = 5.0):
        """
        :param str database_file:
            The name of a file that contains (or will contain) an SQLite
            database holding the data. If omitted, an unshared in-memory
            database will be used (suitable only for testing).
        :param bool read_only:
            Whether the database is in read-only mode. When the database is in
            read-only mode, it *must* already exist.
        :param ddl_file:
            The name of a file (typically containing SQL DDL commands used to
            create the tables) to be evaluated against the database before this
            object completes construction. If ``None``, nothing will be
            evaluated. You probably don't want to specify a DDL file at the
            same time as setting ``read_only=True``.
        :type ddl_file: str or None
        :param row_factory:
            Callable used to create the rows of result sets.
            Either ``tuple`` or ``sqlite3.Row`` (default);
            can be ``None`` to use the DB driver default.
        :type row_factory: ~collections.abc.Callable or None
        :param text_factory:
            Callable used to create the Python values of non-numeric columns
            in result sets. Usually ``memoryview`` (default) but should be
            ``str`` when you're expecting string results;
            can be ``None`` to use the DB driver default.
        :type text_factory: ~collections.abc.Callable or None
        :param bool case_insensitive_like:
            Whether we want the ``LIKE`` matching operator to be case-sensitive
            or case-insensitive (default).
        :param float timeout:
            How many seconds the connection should wait before raising an
            `OperationalError` when a table is locked. If another connection
            opens a transaction to modify a table, that table will be locked
            until the transaction is committed. Default five seconds.
        :param Synchronisation synchronisation:
            The synchronisation level. Doesn't normally need to be altered.
        """
        self.__db = None
        self.__cursor = None
        if database_file is None:
            self.__db = sqlite3.connect(":memory:")  # Magic name!
            # in-memory DB is never read-only
        elif read_only:
            if not os.path.exists(database_file):
                raise FileNotFoundError(f"no such DB: {database_file}")
            db_uri = pathlib.Path(os.path.abspath(database_file)).as_uri()
            # https://stackoverflow.com/a/21794758/301832
            self.__db = sqlite3.connect(
                f"{db_uri}?mode=ro", uri=True, timeout=timeout)
        else:
            self.__db = sqlite3.connect(database_file, timeout=timeout)

        # We want to assume control over transactions ourselves
        self.__db.isolation_level = None

        if row_factory is not None:
            self.__db.row_factory = row_factory
        if text_factory is not None:
            self.__db.text_factory = text_factory

        if not read_only and ddl_file:
            with open(ddl_file, encoding="utf-8") as f:
                sql = f.read()
            self.__db.executescript(sql)
            # Stamp the DB with a schema version, which is the first four
            # bytes of the MD5 hash of the content of the schema file used to
            # set it up. We don't currently validate this at all.
            #
            # The application_id pragma would be used within the DDL schema.
            ddl_hash, = struct.unpack_from(
                ">I", hashlib.md5(sql.encode()).digest())
            self.__pragma("user_version", ddl_hash)
        if case_insensitive_like:
            self.__pragma("case_sensitive_like", False)
        # Official recommendations!
        self.__pragma("foreign_keys", True)
        self.__pragma("recursive_triggers", True)
        self.__pragma("trusted_schema", False)

    def _context_entered(self):
        """
        Work to do when then context is entered.

        May be extended by super classes

        """
        if self.__db is None:
            raise DatabaseException("database has been closed")
        if self.__cursor is not None:
            raise DatabaseException("double cursor")
        if not self.__db.in_transaction:
            self.__db.execute("BEGIN")
        self.__cursor = self.__db.cursor()

    def __enter__(self):
        self._context_entered()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.__db is not None:
            if exc_type is None:
                self.__db.commit()
            else:
                self.__db.rollback()
        self.__cursor = None
        self.close()

    def __del__(self) -> None:
        self.close()

    def close(self) -> None:
        """
        Finalises and closes the database.
        """
        try:
            if self.__db is not None:
                self.__db.close()
                self.__db = None
        except AttributeError:
            self.__db = None

    def __pragma(self, pragma_name: str, value: Union[bool, int, str]):
        """
        Set a database ``PRAGMA``. See the `SQLite PRAGMA documentation
        <https://www.sqlite.org/pragma.html>`_ for details.

        :param str pragma_name:
            The name of the pragma to set.
            *Must be the name of a supported pragma!*
        :param value:
            The value to set the pragma to.
            If a string, must not contain a single quote.
        :type value: bool or int or str
        """
        if not self.__db:
            raise AttributeError("database has been closed")
        if isinstance(value, bool):
            if value:
                self.__db.executescript(f"PRAGMA {pragma_name}=ON;")
            else:
                self.__db.executescript(f"PRAGMA {pragma_name}=OFF;")
        elif isinstance(value, int):
            self.__db.executescript(f"PRAGMA {pragma_name}={int(value)};")
        elif isinstance(value, str):
            if "'" in value:  # Safety check!
                raise PacmanValueError(
                    "DB pragma values must not contain single quotes")
            self.__db.executescript(f"PRAGMA {pragma_name}='{str(value)}';")
        else:
            raise TypeError("can only set pragmas to bool, int or str")

    def execute(self, sql, parameters=()):
        """
        Executes a query by passing it to the database

        :param str sql:
        :param parameters:
        :raises DatabaseException: If there is no cursor.
            Typically because database was used outside of a with
        """
        if self.__cursor is None:
            raise DatabaseException(
                "This method should only be used inside a with")
        return self.__cursor.execute(sql, parameters)

    def executemany(self, sql, parameters=()):
        """
        Repeatedly executes a query by passing it to the database

        :param str sql:
        :param parameters:
        :raises DatabaseException: If there is no cursor.
            Typically because database was used outside of a with
        """
        if self.__cursor is None:
            raise DatabaseException(
                "This method should only be used inside a with")
        return self.__cursor.executemany(sql, parameters)

    @property
    def lastrowid(self) -> int:
        """
        Gets the lastrowid from the last query run/ execute

        :rtype: int
        :raises DatabaseException: If there is no cursor.
            Typically because database was used outside of a with
        """
        if self.__cursor is None:
            raise DatabaseException(
                "This method should only be used inside a with")
        return self.__cursor.lastrowid

    @property
    def rowcount(self) -> int:
        """
        Gets the rowcount from the last query run/ execute

        :rtype: int
        :raises DatabaseException: If there is no cursor.
            Typically because database was used outside of a with
        """
        if self.__cursor is None:
            raise DatabaseException(
                "This method should only be used inside a with")
        return self.__cursor.rowcount

    def fetchone(self):
        """
        Gets the fetchone from the last query run

        :raises DatabaseException: If there is no cursor.
            Typically because database was used outside of a with
        """
        if self.__cursor is None:
            raise DatabaseException(
                "This method should only be used inside a with")
        return self.__cursor.fetchone()
