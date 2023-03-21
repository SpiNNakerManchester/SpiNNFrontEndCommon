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

from contextlib import AbstractContextManager as ACMBase
import enum
import hashlib
import logging
import os
import pathlib
import sqlite3
import struct
from spinn_utilities.abstract_context_manager import AbstractContextManager
from spinn_utilities.logger_utils import warn_once
logger = logging.getLogger(__name__)


class Isolation(enum.Enum):
    """
    Transaction isolation levels for :py:meth:`SQLiteDB.transaction`.
    """
    #: Standard transaction type; postpones holding a lock until required.
    DEFERRED = "DEFERRED"
    #: Take the lock immediately; this may be a read-lock that gets upgraded.
    IMMEDIATE = "IMMEDIATE"
    #: Take a write lock immediately. This is the strongest lock type.
    EXCLUSIVE = "EXCLUSIVE"


class SQLiteDB(AbstractContextManager):
    """
    General support class for SQLite databases. This handles a lot of the
    low-level detail of setting up a connection.

    Basic usage (with the default row type)::

        with SQLiteDB("db_file.sqlite3") as db:
            with db.transaction() as cursor:
                for row in cursor.execute("SELECT thing FROM ..."):
                    print(row["thing"])

    This class is designed to be either used as above or by subclassing.
    See the `SQLite SQL documentation <https://www.sqlite.org/lang.html>`_ for
    details of how to write queries, and the Python :py:mod:`sqlite3` module
    for how to do parameter binding.
    """

    __slots__ = [
        # the database holding the data to store
        "__db",
    ]

    def __init__(self, database_file=None, *, read_only=False, ddl_file=None,
                 row_factory=sqlite3.Row, text_factory=memoryview,
                 case_insensitive_like=True):
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
        """
        self.__db = None
        if database_file is None:
            self.__db = sqlite3.connect(":memory:")  # Magic name!
            # in-memory DB is never read-only
        elif read_only:
            if not os.path.exists(database_file):
                raise FileNotFoundError(f"no such DB: {database_file}")
            db_uri = pathlib.Path(os.path.abspath(database_file)).as_uri()
            # https://stackoverflow.com/a/21794758/301832
            self.__db = sqlite3.connect(f"{db_uri}?mode=ro", uri=True)
        else:
            self.__db = sqlite3.connect(database_file)

        if row_factory:
            self.__db.row_factory = row_factory
        if text_factory:
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
            self.pragma("user_version", ddl_hash)
        if case_insensitive_like:
            self.pragma("case_sensitive_like", False)
        # Official recommendations!
        self.pragma("foreign_keys", True)
        self.pragma("recursive_triggers", True)
        self.pragma("trusted_schema", False)

    def __del__(self):
        self.close()

    def close(self):
        """
        Finalises and closes the database.
        """
        try:
            if self.__db is not None:
                self.__db.close()
                self.__db = None
        except AttributeError:
            self.__db = None

    def pragma(self, pragma_name, value):
        """
        Set a database ``PRAGMA``. See the `SQLite PRAGMA documentation
        <https://www.sqlite.org/pragma.html>`_ for details.

        :param str pragma_name:
            The name of the pragma to set.
        :param value:
            The value to set the pragma to.
        :type value: bool or int or str
        """
        if isinstance(value, bool):
            if value:
                self.__db.executescript(f"PRAGMA {pragma_name}=ON;")
            else:
                self.__db.executescript(f"PRAGMA {pragma_name}=OFF;")
        elif isinstance(value, int):
            self.__db.executescript(f"PRAGMA {pragma_name}={value};")
        elif isinstance(value, str):
            self.__db.executescript(f"PRAGMA {pragma_name}='{value}';")
        else:
            raise TypeError("can only set pragmas to bool, int or str")

    @property
    def connection(self):
        """
        The underlying SQLite database connection.

        .. warning::
            If you're using this a lot, consider contacting the SpiNNaker
            Software Team with details of your use case so we can extend the
            relevant core class to support you. *Normally* it is better to use
            :py:meth:`transaction` to obtain a cursor with appropriate
            transactional guards.

        :rtype: ~sqlite3.Connection
        :raises AttributeError: if the database connection has been closed
        """
        warn_once(
            logger,
            "Low-level connection used instead of transaction() context. "
            "Please contact SpiNNaker Software Team with your use-case for "
            "assistance.")
        if not self.__db:
            raise AttributeError("database has been closed")
        return self.__db

    def transaction(self, isolation_level=None):
        """
        Get a context manager that manages a transaction on the database.
        The value of the context manager is a :py:class:`~sqlite3.Cursor`.
        This means you can do this::

            with db.transaction() as cursor:
                cursor.execute(...)

        :param Isolation isolation_level:
            The transaction isolation level.

            .. note::
                This sets it for the connection!
                Can usually be *not* specified.
        :rtype: ~typing.ContextManager(~sqlite3.Cursor)
        """
        if not self.__db:
            raise AttributeError("database has been closed")
        db = self.__db
        if isolation_level:
            db.isolation_level = isolation_level.value
        return _DbWrapper(db)


class _DbWrapper(ACMBase):
    def __init__(self, db):
        self.__d = db

    def __enter__(self):
        self.__d.__enter__()
        return self.__d.cursor()

    def __exit__(self, exc_type, exc_value, traceback):
        return self.__d.__exit__(exc_type, exc_value, traceback)
